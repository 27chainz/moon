import os
import csv
import whisper

# Paths setup
AUDIO_FOLDER = "data/cleaned_wavs"
OUTPUT_CSV = "data/metadata.csv"

def transcribe_dataset():
    # 1. Load the local Whisper model (using 'base' for a great balance of speed and accuracy)
    print("🧠 Loading local Whisper AI engine... (This may take a moment on first run)")
    model = whisper.load_model("base")
    
    # 2. Gather and sort all our sliced wav files
    wav_files = [f for f in os.listdir(AUDIO_FOLDER) if f.endswith('.wav')]
    wav_files.sort() # Keeps them in numerical order (001, 002, etc.)
    
    if not wav_files:
        print(f"❌ No .wav files found in {AUDIO_FOLDER}!")
        return
        
    print(f"🎙️ Found {len(wav_files)} clips. Starting auto-transcription and context mapping...")
    
    # 3. Open the CSV file and write the header columns
    with open(OUTPUT_CSV, mode='w', newline='', encoding='utf-8') as csv_file:
        fieldnames = ['file_name', 'text', 'emotion', 'pacing', 'intensity']
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        
        # 4. Loop through every single file and process it
        for index, file_name in enumerate(wav_files):
            file_path = os.path.join(AUDIO_FOLDER, file_name)
            print(f"⚡ Processing [{index + 1}/{len(wav_files)}]: {file_name}...")
            
            try:
                # Let Whisper listen and transcribe
                result = model.transcribe(file_path, fp16=False)
                clean_text = result["text"].strip()
                
                # Automatically inject our emotional conditioning metadata context!
                writer.writerow({
                    'file_name': file_name,
                    'text': clean_text,
                    'emotion': 'Fear_Vulnerable',
                    'pacing': 'Dynamic_Anxious',
                    'intensity': 'High'
                })
            except Exception as e:
                print(f"⚠️ Failed to transcribe {file_name}. Error: {e}")
                
    print(f"\n🚀 Master Dataset Created Successfully!")
    print(f"📊 Check your new dataset file at: {OUTPUT_CSV}")

if __name__ == "__main__":
    transcribe_dataset()