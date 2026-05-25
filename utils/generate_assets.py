import wave, struct, math, os

def create_hmm_wav():
    os.makedirs("assets", exist_ok=True)
    path = "assets/hmm.wav"
    with wave.open(path, "w") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(22050)
        samples = [
            int(600 * math.sin(2 * math.pi * 200 * i / 22050) * math.exp(-i / 4000))
            for i in range(10000)
        ]
        f.writeframes(struct.pack("<" + "h" * len(samples), *samples))
    print("ARIA: Created assets/hmm.wav")

if __name__ == "__main__":
    create_hmm_wav()
