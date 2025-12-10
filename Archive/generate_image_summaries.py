import json
import io
import os
from PIL import Image
import torch
from transformers import Qwen2VLForConditionalGeneration, AutoProcessor
from qwen_vl_utils import process_vision_info

MODEL_ID = "Qwen/Qwen2-VL-2B-Instruct"
model = None
processor = None

def get_vision_model():
    global processor, model
    if model is None:
        print(f"Loading AI Vision Model ({MODEL_ID})...")
        device = "cuda" if torch.cuda.is_available() else "cpu"
        model = Qwen2VLForConditionalGeneration.from_pretrained(
            MODEL_ID, 
            torch_dtype=torch.float16 if device == "cuda" else torch.float32, 
            device_map="auto"
        )
        processor = AutoProcessor.from_pretrained(MODEL_ID)
    return processor, model

def generate_image_summary(image_path):
    try:
        processor, model = get_vision_model()
        raw_image = Image.open(image_path).convert('RGB')
        
        prompt_text = (
            "Analyze this technical image from software documentation. "
            "Provide a concise summary describing what the image shows."
        )

        messages = [{
            "role": "user",
            "content": [
                {"type": "image", "image": raw_image},
                {"type": "text", "text": prompt_text},
            ],
        }]

        text_inputs = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        image_inputs, video_inputs = process_vision_info(messages)
        inputs = processor(
            text=[text_inputs],
            images=image_inputs,
            videos=video_inputs,
            padding=True,
            return_tensors="pt",
        ).to(model.device)

        generated_ids = model.generate(**inputs, max_new_tokens=256)
        generated_ids_trimmed = [
            out_ids[len(in_ids):] for in_ids, out_ids in zip(inputs.input_ids, generated_ids)
        ]
        description = processor.batch_decode(
            generated_ids_trimmed, skip_special_tokens=True, clean_up_tokenization_spaces=False
        )[0]

        return description
    except Exception as e:
        print(f"Error processing image: {e}")
        return None

with open('confluence_attachments/download_summary.json', 'r') as f:
    data = json.load(f)

for i, entry in enumerate(data):
    if 'summary' in entry:
        print(f"[{i+1}/{len(data)}] Skipping (already has summary): {entry['image_name']}")
        continue
        
    img_path = f"confluence_attachments/{entry['local_directory']}/{entry['image_name']}"
    
    if not os.path.exists(img_path):
        print(f"[{i+1}/{len(data)}] File not found, skipping: {entry['image_name']}")
        continue
        
    print(f"[{i+1}/{len(data)}] Processing: {entry['image_name']}")
    
    summary = generate_image_summary(img_path)
    if summary:
        entry['summary'] = summary
    
    with open('confluence_attachments/download_summary.json', 'w') as f:
        json.dump(data, f, indent=4)

print("Done!")
