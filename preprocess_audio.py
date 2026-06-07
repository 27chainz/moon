import os
from pydub import AudioSegment
from pydub.effects import normalize
from pydub.silence import detect_nonsilent
from tqdm import tqdm

def high_pass_filter(audio, cutoff_freq=80):
    """Removes low-end thuds, mic rumbles, and heavy plosive wind hits."""
    return audio.high_pass_filter(cutoff_freq)

def trim_silence(audio, silence_thresh=-40, chunk_size=10):
    """Locates the true audio boundaries and strips dead space from edges."""
    keep_chunks = detect_nonsilent(
        audio, 
        min_silence_len=chunk_size, 
        silence_thresh=silence_thresh
    )
    if keep_chunks:
        start_time = keep_chunks[0][0]
        end_time = keep_chunks[-1][1]
        return audio[start_time:end_time]
    return audio

def process_voice_file(input_path, output_path):
    """Executes the full structural cleaning pipeline on a single file."""
    try:
        # 1. Load the raw source file
        raw_audio = AudioSegment.from_file(input_path)
        
        # 2. Run the digital filters
        filtered_audio = high_pass_filter(raw_audio, cutoff_freq=80)
        trimmed_audio = trim_silence(filtered_audio, silence_thresh=-45)
        normalized_audio = normalize(trimmed_audio, headroom=0.1)
        
        # 3. Standardize format to 24000Hz Mono for DramaBox execution
        final_audio = normalized_audio.set_frame_rate(24000).set_channels(1)
        
        # 4. Export clean wave file
        final_audio.export(output_path, format="wav")
        return True
    except Exception as e:
        print(f"⚠️ Error processing {os.path.basename(input_path)}: {str(e)}")
        return False

def run_pipeline():
    # Setup our source and destination directories
    input_dir = "data/raw_source"
    output_dir = "data/cleaned_wavs"
    
    os.makedirs(input_dir, exist_ok=True)
    os.makedirs(output_dir, exist_ok=True)
    
    # Check for files
    supported_formats = ('.wav', '.mp3', '.m4a', '.flac')
    files_to_process = [f for f in os.listdir(input_dir) if f.lower().endswith(supported_formats)]
    
    if not files_to_process:
        print(f"\n📂 Source folder '{input_dir}' is currently empty!")
        print("👉 Drop some raw recordings (mp3, wav, etc.) in there and run this script again.")
        return

    print(f"⚡ Found {len(files_to_process)} raw source files. Initiating audio polish...")
    
    success_count = 0
    for file_name in tqdm(files_to_process, desc="Processing Audio Layers"):
        in_path = os.path.join(input_dir, file_name)
        # Convert any incoming extension cleanly to standard .wav
        out_name = os.path.splitext(file_name)[0] + "_cleaned.wav"
        out_path = os.path.join(output_dir, out_name)
        
        if process_voice_file(in_path, out_path):
            success_count += 1
            
    print(f"\n🎉 Pipeline Complete! Cleaned {success_count}/{len(files_to_process)} files.")
    print(f"📁 Your pristine training assets are ready in: '{output_dir}'")

if __name__ == "__main__":
    run_pipeline()