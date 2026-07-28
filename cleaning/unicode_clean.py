import unicodedata

def normalize_unicode(text:str)->str:

    text = unicodedata.normalize("NFKC",text)
    return text