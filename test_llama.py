import subprocess

def call_llm(prompt):
    result = subprocess.run(
        ["ollama", "run", "llama3"],
        input=prompt,
        text=True,
        capture_output=True
    )
    return result.stdout

if __name__ == "__main__":
    cevap = call_llm("Bundan sonra tüm cevaplarını Türkçe ver.Teknik konularda açık ve doğru anlat.Gradient descent nedir? 2 cümle.")
    print(cevap)
