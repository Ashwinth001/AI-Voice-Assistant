import urllib.request, os, sys

VOICE    = "en_US-amy-medium"
BASE_URL = "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/amy/medium"
OUT_DIR  = "assets/voices"

def download():
    os.makedirs(OUT_DIR, exist_ok=True)
    files = [
        (BASE_URL + "/" + VOICE + ".onnx",      OUT_DIR + "/" + VOICE + ".onnx"),
        (BASE_URL + "/" + VOICE + ".onnx.json", OUT_DIR + "/" + VOICE + ".onnx.json"),
    ]
    for url, dest in files:
        if os.path.exists(dest):
            print("ARIA: Already exists: " + dest)
            continue
        print("ARIA: Downloading " + os.path.basename(dest) + " ...")
        try:
            urllib.request.urlretrieve(url, dest)
            print("ARIA: Saved " + dest)
        except Exception as e:
            print("ARIA: WARNING - download failed: " + str(e))
            print("ARIA: Download manually from https://huggingface.co/rhasspy/piper-voices")

if __name__ == "__main__":
    download()
