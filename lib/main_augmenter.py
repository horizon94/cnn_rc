    # coding: utf-8
import numpy as np
import re
import math
import word2vec
import logging
import pickle 
from keras.models import Model
from keras.layers import Dense, Activation, Embedding, Input, merge, Flatten, Reshape
from keras.layers import Convolution1D as Conv1D
from keras.layers.core import Dropout
from keras.layers.pooling import MaxPooling1D

import keras.backend.tensorflow_backend as K
    
from keras.regularizers import l2
from keras.callbacks import TensorBoard
from keras import backend as K
from keras.optimizers import Adadelta
from keras.utils.np_utils import to_categorical

from sklearn.model_selection import KFold

from .supersense import SupersenseLookup
from .functions import *
from .model import get_model, train_model
from .pretrained_model import get_pretrained_model

from .argparser import build_argparser


def main(args):
    ########## Parse arguments and setup logging ####################
    #################################################################
   # with K.tf.device('/gpu:0'):
    loglevel = logging.DEBUG if args.debug else logging.INFO

    logging.basicConfig(
        level=loglevel,
        format="[%(asctime)s] %(levelname)s:%(message)s")


    WINDOW_SIZE = args.filter_size
    WINDOW_HEIGHT = args.window_sizes

    FOLDS = args.folds 
    EPOCHS = args.epochs
    DEBUG = args.debug
    TEST_FILE = args.test_file
    DROPOUT_RATE = args.dropoutrate
    INCLUDE_POS_EMB = not args.no_pos
    WORD_EMBEDDING_DIMENSION = args.wordembeddingdim
    INCLUDE_ATTENTION_ONE = args.attention_one
    INCLUDE_ATTENTION_TWO = args.attention_two
    POS_EMBEDDING_DIM = args.posembeddingdim
    L2_VALUE = args.l2
    TRAIN_FILE = args.train_file
    EXCLUDE_OTHER = args.exclude_other
    INCLUDE_WORDNET = args.wordnet
    EMBEDDING = args.embedding
    CLIPPING_VALUE = args.clipping
    DATASET = args.dataset

    objectives = { "categorical_crossentropy" : "categorical_crossentropy"  }
    OBJECTIVE = objectives[args.loss]

    ########## Load embeddings, dataset and prep input ####################
    #######################################################################
    if EMBEDDING == 'word2vec':
        word_embeddings = word2vec.load("word_embeddings.bin", encoding='ISO-8859-1')
        fit_str = ""
        for word in word_embeddings.vocab:
            fit_str += word + " "
    elif EMBEDDING == 'glove':
        word_embeddings = pickle.load(open("glove300b.pkl", "rb"))
        

    elif EMBEDDING == 'rand':
        word_embeddings = {}

    if DATASET == 'semeval':
        from .semeval.prep import Preprocessor, output_dict, reverse_dict   
        prep = Preprocessor(clipping_value=CLIPPING_VALUE)

        dataset_full, labels_full = prep.read_dataset(TRAIN_FILE, debug=DEBUG,
                                                  EXCLUDE_OTHER=EXCLUDE_OTHER)
    elif DATASET == 'ace2005':
        from .ace2005.prep import AcePrep
        prep = AcePrep(clipping_value=CLIPPING_VALUE)



        dataset_full, labels_full = prep.read_dataset(TRAIN_FILE, debug=DEBUG)
        output_dict = [0,1,2,3,4,5,6]


    #### Compute number of output classes #################################

    no_of_clz = len(output_dict)

    NO_OF_CLASSES = no_of_clz - 1 if args.exclude_other else no_of_clz


    logging.info("#" * 30)
    logging.info("DATA SPLIT AND LOADED")
    logging.info("#" * 30)


    (word_input, nom_pos_1, nom_pos_2, 
        _, att_list_1, att_list_2,
        Y) = prep.fit_transform(dataset_full, labels_full)

    att_list_1 = []
    att_list_2 = []

    word_index = prep.word_idx()
    clipping_value = prep.clipping_value

    #clipping_value = len(max(word_input, key=len))

    ###### Beginning official test #########
    
    logging.info("Beginning test with official F1 scorer ...")

    test_path = "data/semeval/testing/" + TEST_FILE + ".txt"

    test_set = open(test_path)


    data, clzz, flip_clz = prep.read_semiset(test_set, EXCLUDE_OTHER=EXCLUDE_OTHER)

    ids = [i for i in range(0, len(data))]
 
    X_train = [word_input]
    X_backup = X_train

    wordnet_sequences = []

    build_input_arrays_test(X_train,
                            att_list_1, att_list_2,
                            nom_pos_1, nom_pos_2,
                            wordnet_sequences)


    Y_train = build_label_representation(Y, OBJECTIVE=OBJECTIVE,
                                NO_OF_CLASSES=NO_OF_CLASSES,
                                WINDOW_SIZE=WINDOW_SIZE)
    Y_backup = Y_train

    model = get_model( 
        word_embeddings=word_embeddings,
        word_index=word_index, 
        n=clipping_value,
        POS_EMBEDDING_DIM=POS_EMBEDDING_DIM,
        L2_VALUE=L2_VALUE,
        WORD_EMBEDDING_DIM=WORD_EMBEDDING_DIMENSION,
        WINDOW_HEIGHT=WINDOW_HEIGHT,
        WORDNET=INCLUDE_WORDNET,
        WORDNET_LEN=0,
        DROPOUT_RATE=DROPOUT_RATE,
        WINDOW_SIZE=WINDOW_SIZE,
        NO_OF_CLASSES=NO_OF_CLASSES,
        optimizer=args.optimizer,
        loss=OBJECTIVE
        )

  


    logging.info(model.summary())

    result = train_model(model, X_train, Y_train, EPOCHS, early_stopping=True)
    model = get_model( 
        word_embeddings=word_embeddings,
        word_index=word_index, 
        n=clipping_value,
        POS_EMBEDDING_DIM=POS_EMBEDDING_DIM,
        L2_VALUE=L2_VALUE,
        WORD_EMBEDDING_DIM=WORD_EMBEDDING_DIMENSION,
        WINDOW_HEIGHT=WINDOW_HEIGHT,
        WORDNET=INCLUDE_WORDNET,
        WORDNET_LEN=0,
        DROPOUT_RATE=DROPOUT_RATE,
        WINDOW_SIZE=WINDOW_SIZE,
        NO_OF_CLASSES=NO_OF_CLASSES,
        optimizer=args.optimizer,
        loss=OBJECTIVE
        )

    best_epoch = np.argmin(np.asarray(result.history['val_loss']))

    logging.info("Training with " + str(best_epoch) + " epochs by early stopping")
    
    result = train_model(model, X_train, Y_train, best_epoch, early_stopping=False)



    logging.info("Done training...")

    ########## Prepare test data                  #########################
    #######################################################################


    #aux_texts = [fit_str]
    aux_texts = None
    (X_test, X_test_nom_pos1, X_test_nom_pos2, _, 
        att_test_list_1, att_test_list_2, kept_ids) = prep.transform(data,ids, aux_texts=aux_texts)

    word_idx = prep.word_idx()


    # if aux_texts:
    #     all_weights = model.get_weights()

    #     embedding_weights = all_weights[0]

    #     pretrained_emb_index = embedding_weights.shape[0]

    #     new_embedding_list = []

    #     for word, idx in list(word_index.items()):
    #         if idx < pretrained_emb_index:
    #             continue
    #         try:
    #             embedding_vector = word_embeddings[word]
    #         except:
    #             embedding_vector = np.random.uniform(-0.25, 0.25, 300)
    #         finally:
    #             new_embedding_list.append(embedding_vector)

    #     new_embedding = np.append(embedding_weights, np.asarray(new_embedding_list), axis = 0)

    #     old_model = model 


    #     all_weights[0] = new_embedding

    # model = get_pretrained_model({},clipping_value, WORD_EMBEDDING_DIM=300,
    #     POS_EMBEDDING_DIM=50, L2_VALUE=L2_VALUE, WINDOW_HEIGHT=WINDOW_HEIGHT,
    #     WINDOW_SIZE=WINDOW_SIZE, DROPOUT_RATE=DROPOUT_RATE,
    #     all_weights=all_weights
    #     )

    # import ipdb
    # ipdb.sset_trace()

    # model.save("newest.model")
    # import pickle
    # pickle.dump(prep, open("prepper.pkl", 'wb'))

    X = [X_test]

    att_test_list_1 = []
    att_test_list_2 = []


    build_input_arrays_test(X,
                            att_test_list_1, att_test_list_2,
                            X_test_nom_pos1, X_test_nom_pos2,
                            wordnet_sequences)

    #failures = [x for x in ids if x not in kept_ids]

    logging.info("Predicting for X...")    
    
    preds = []
    fails = []

    for i in range(0, len(X_test)):
        try:
            preds.append(model.predict([X_test[i:i+1], X_test_nom_pos1[i:i+1], X_test_nom_pos2[i:i+1]]))
        except:
            fails.append(i)



    import pickle

    all_data = [data, clzz, flip_clz, kept_ids, fails, preds] 

    pickle.dump(all_data, open("all_data.pkl", "wb"))


    # import ipdb
    # ipdb.sset_trace()


    # preds_final = [np.argmax(pred) for pred in preds]

    # lookup_labels = [reverse_dict[pred] for pred in preds_final]

    # with open("data/semeval/test_pred.txt", "w+") as f:
    #     for idx, i in enumerate(kept_ids):
    #         f.write(i + "\t" + lookup_labels[idx] + "\n")

    #     for i in failures:
    #         f.write(i + "\t" + "Other" + "\n")



    logging.info("Experiment done!")

if __name__ == '__main__':
    parser = build_argparser()
    args = parser.parse_args()
    main(args)