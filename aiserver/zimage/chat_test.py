import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
import sys

# Model paths
MODEL_PATH = "/mnt/hdd/models/Z-Image-Turbo/text_encoder"
TOKENIZER_PATH = "/mnt/hdd/models/Z-Image-Turbo/tokenizer"

def main():
    print(f"Loading tokenizer from {TOKENIZER_PATH}...")
    try:
        tokenizer = AutoTokenizer.from_pretrained(TOKENIZER_PATH)
    except Exception as e:
        print(f"Error loading tokenizer: {e}")
        return

    print(f"Loading model from {MODEL_PATH}...")
    try:
        # Load model with bfloat16 and auto device map (to use GPU if available)
        model = AutoModelForCausalLM.from_pretrained(
            MODEL_PATH,
            torch_dtype=torch.bfloat16,
            device_map="auto"
        )
    except Exception as e:
        print(f"Error loading model: {e}")
        return

    print("\nModel loaded successfully! Starting chat...")
    print("Type 'exit', 'quit', or 'q' to end the session.\n")

    messages = [
        {"role": "system", "content": "You are a helpful assistant."}
    ]

    # Check for command line arguments
    if len(sys.argv) > 1:
        initial_prompt = sys.argv[1]
        print(f"User: {initial_prompt}")
        messages.append({"role": "user", "content": initial_prompt})
        try:
            # Apply chat template
            text = tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True
            )
            
            model_inputs = tokenizer([text], return_tensors="pt").to(model.device)

            # Generate response
            with torch.no_grad():
                generated_ids = model.generate(
                    **model_inputs,
                    max_new_tokens=512,
                    do_sample=True,
                    temperature=0.7,
                    top_p=0.9
                )
            
            # Decode response
            generated_ids = [
                output_ids[len(input_ids):] for input_ids, output_ids in zip(model_inputs.input_ids, generated_ids)
            ]
            response = tokenizer.batch_decode(generated_ids, skip_special_tokens=True)[0]

            print(f"Assistant: {response}\n")
            return # Exit after single response
        except Exception as e:
            print(f"Error during generation: {e}")
            return

    while True:
        try:
            user_input = input("User: ")
        except KeyboardInterrupt:
            print("\nExiting...")
            break

        if user_input.lower() in ["exit", "quit", "q"]:
            break
        
        if not user_input.strip():
            continue

        messages.append({"role": "user", "content": user_input})

        try:
            # Apply chat template
            text = tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True
            )
            
            model_inputs = tokenizer([text], return_tensors="pt").to(model.device)

            # Generate response
            with torch.no_grad():
                generated_ids = model.generate(
                    **model_inputs,
                    max_new_tokens=512,
                    do_sample=True,
                    temperature=0.7,
                    top_p=0.9
                )
            
            # Decode response
            generated_ids = [
                output_ids[len(input_ids):] for input_ids, output_ids in zip(model_inputs.input_ids, generated_ids)
            ]
            response = tokenizer.batch_decode(generated_ids, skip_special_tokens=True)[0]

            print(f"Assistant: {response}\n")
            
            messages.append({"role": "assistant", "content": response})
            
        except Exception as e:
            print(f"Error during generation: {e}")

if __name__ == "__main__":
    main()

