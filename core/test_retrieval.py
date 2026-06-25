from memory import Memory, calculate_importance
from retrieval import RetrievalEngine
from sentence_transformers import SentenceTransformer

def run_test():
    print("正在加载 MiniLM...")
    model = SentenceTransformer('all-MiniLM-L6-v2')

    # 1. 制造几段毫不相干的假记忆
    texts = [
        "Kayla ate a delicious piece of toast for breakfast.",
        "Kayla is reading 'One Hundred Years of Solitude' by the window.",
        "Kayla is playing intense video games in her room."
    ]

    print("正在把句子压缩成高维向量并调用 LLM 计算重要性...")
    memories = []
    for i, text in enumerate(texts):
        vector = model.encode(text) 
        score = calculate_importance(text)
        print(f"[{score}分] {text}")
        
        mem = Memory(memory_id=f"m{i}", text=text, importance_score=score, embedding_vector=vector)
        memories.append(mem)

    # 2. 扔出一个检索 Query
    query_text = "What might be Kayla's fav book?"
    
    query_vector = model.encode(query_text) 

    # 3. 引擎启动，算余弦相似度并召回
    engine = RetrievalEngine()
    print("\n启动检索引擎... 正在计算 衰减 + 相似度 + 重要性综合得分...")
    results = engine.retrieve(memories, query_vector, top_k=2)

    print("\n====== 检索到的最相关的 Top-2 记忆 ======")
    for res in results:
        print(f"-> {res.text} (重要性: {res.importance_score}分)")

if __name__ == "__main__":
    run_test()
