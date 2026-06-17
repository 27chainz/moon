import os
import torch
import soundfile as sf

# 🛠️ THE HOT-PATCH: Intercept and bypass torchaudio's broken load system
import torchaudio
def soundfile_load_patch(filepath, *args, **kwargs):
    data, samplerate = sf.read(filepath, dtype='float32')
    # Convert soundfile's [samples, channels] to torch's [channels, samples]
    tensor = torch.FloatTensor(data).t()
    if tensor.ndim == 1:
        tensor = tensor.unsqueeze(0)
    return tensor, samplerate

torchaudio.load = soundfile_load_patch

# Now import F5 cleanly
from f5_tts.api import F5TTS

def generate_voice():
    print("📡 Booting up local F5-TTS Engine...")
    f5tts = F5TTS()
    
    ref_audio = "data/cleaned_wavs/M1_fear_015.wav"
    ref_text = "I freaked. I didn't know what to do."
    gen_text = "Please, just stop. If they find out we're down here... I don't know what they'll do to us."
    
    output_dir = "data/generated_tests"
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "f5_fear_test.wav")
    
    print("🧬 Synthesizing audio locally using soundfile patch...")
    f5tts.infer(
        ref_file=ref_audio,
        ref_text=ref_text,
        gen_text=gen_text,
        file_wave=output_path
    )
    
    print(f"🎉 File successfully baked at: {output_path}")

if __name__ == "__main__":
    generate_voice()