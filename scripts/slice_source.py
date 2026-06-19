import os
import subprocess
from pydub import AudioSegment
from pydub.silence import split_on_silence

# Paths setup
AudioSegment.converter = os.path.abspath("ffmpeg.exe")
AudioSegment.ffprobe = os.path.abspath("ffprobe.exe")

RAW_FOLDER = "data/raw_source"
OUTPUT_FOLDER = "data/cleaned_wavs"
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

def slice_audio():
    files = [f for f in os.listdir(RAW_FOLDER) if f.endswith('.mp3')]
    if not files:
        print("❌ No .mp3 files found in data/raw_source!")
        return
    
    input_file = os.path.join(RAW_FOLDER, files[0])
    denoised_temp = os.path.join(RAW_FOLDER, "temp_denoised.wav")
    
    print(f"🎬 Found raw source: {files[0]}")
    print("🤫 Running FFmpeg FFT De-Noiser...")
    
    try:
        subprocess.run([
            "ffmpeg", "-y", "-i", input_file, 
            "-af", "afftdn=nf=-35", # Slightly more aggressive noise reduction floor
            "-ar", "24000", "-ac", "1", 
            denoised_temp
        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        print(f"⚠️ FFmpeg de-noising failed, using original file. Error: {e}")
        denoised_temp = input_file

    print("✂️ Slicing audio on dynamic emotional pauses...")
    audio = AudioSegment.from_file(denoised_temp)
    
    # FINE-TUNED FOR EMOTIONAL DIALOGUE 🎯
    chunks = split_on_silence(
        audio,
        min_silence_len=300,   # Dropped from 1000ms to 300ms to catch natural breath pauses
        silence_thresh=-38,    # Raised threshold to ignore that early background noise floor
        keep_silence=150       # Leaves a tight 150ms natural breath cushion
    )
    
    print(f"📦 Successfully cut into {len(chunks)} custom sentence clips!")
    
    # Export each chunk
    for i, chunk in enumerate(chunks):
        # Ignore accidental micro-clips that are less than 0.8 seconds (usually just a lip smack or click)
        if len(chunk) < 800:
            continue
            
        output_filename = f"M1_fear_{i+1:03d}.wav"
        output_path = os.path.join(OUTPUT_FOLDER, output_filename)
        chunk.export(output_path, format="wav")
        
    if os.path.exists(os.path.join(RAW_FOLDER, "temp_denoised.wav")):
        os.remove(os.path.join(RAW_FOLDER, "temp_denoised.wav"))
        
    print(f"🚀 All optimized clips saved to '{OUTPUT_FOLDER}/'!")

if __name__ == "__main__":
    slice_audio()