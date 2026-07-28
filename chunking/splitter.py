from langchain_text_splitters import RecursiveCharacterTextSplitter

from preprocessing.config import(CHUNK_SIZE, CHUNK_OVERLAP)

splitter = RecursiveCharacterTextSplitter(
    chunk_size = CHUNK_SIZE,
    chunk_overlap = CHUNK_OVERLAP,
    separators = ["\n\n","\n",". "," ",""]
)

def split_text(text:str) ->list[str]:
    """ Split text into overlapping chunks """
    return splitter.split_text(text)

if __name__ == "__main__":
    sample = ("This is a sample judgement.\n"*500)
    chunks = split_text(sample)
    print(f"Total Chunks : {len(chunks)}")


    print("\nFirst Chunk\n")
    print(chunks[0])