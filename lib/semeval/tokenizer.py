from collections import defaultdict
import re


class SemevalTokenizer():

    def __init__(self, vocab=None):
        self.e_reg = "(<e1>|</e1>|<e2>|</e2>)*"
        self.filters='!"#$%&()*+,-.:;=?@[\\]^_`{|}~\t\n'
        self.word_index = defaultdict(int)

        self.vocab = vocab

        self.reverse_index = defaultdict(str)
    
    def fit_on_texts(self,texts):
        for text in texts:
            self._fit(text)

    def _split(self, text):

        text = text.translate(str.maketrans(self.filters, " " * len(self.filters)))
        return [d.strip() for d in text.split(" ") if d.strip()]

    def _fit(self, text):
        text = re.sub(self.e_reg, "", text)
        for token in self._split(text): 
            # try:
            #     word_idx = self.vocab.index(n_token)
                
            if token not in self.word_index:
                n_length = len(self.word_index) + 1
                self.word_index[token] = n_length
                self.reverse_index[n_length] = token

    def sequence(self, texts):
        return [self._sequence(text) for text in texts]

    def _sequence(self, text):

        nom_1 = nom_2 = -1
        seq_arr = []
        
        for idx, token in enumerate(self._split(text)):
            if 'e1' in token:
                nom_1 = idx
                token = re.sub(self.e_reg, "", token)
            elif 'e2' in token:
                nom_2 = idx
                token = re.sub(self.e_reg, "", token)


            ## When we are not fitting, we want an OOV-value instead
            if token not in self.word_index:
                self.word_index[token] = 0
            
            seq_arr.append(self.word_index[token])
            
        return (seq_arr, (nom_1, nom_2))



