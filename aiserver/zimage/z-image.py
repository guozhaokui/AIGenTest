import torch
from diffusers import ZImagePipeline
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from io import BytesIO
import uvicorn
from fastapi.responses import Response

# Initialize FastAPI app
app = FastAPI(title="Z-Image API")

# Load model globally to avoid reloading on every request
print("Loading Z-Image-Turbo model...")
try:
    pipe = ZImagePipeline.from_pretrained(
        "/mnt/hdd/models/Z-Image-Turbo",
        torch_dtype=torch.bfloat16,
        low_cpu_mem_usage=False,
    )
    pipe.to("cuda")
    
    # [Optional] Attention Backend
    # Diffusers uses SDPA by default. Switch to Flash Attention for better efficiency if supported:
    # pipe.transformer.set_attention_backend("flash")    # Enable Flash-Attention-2
    # pipe.transformer.set_attention_backend("_flash_3") # Enable Flash-Attention-3
    
    # [Optional] Model Compilation
    # pipe.transformer.compile()
    
    print("Model loaded successfully.")
except Exception as e:
    print(f"Error loading model: {e}")
    raise e

class GenerateRequest(BaseModel):
    prompt: str
    height: int = 1024
    width: int = 1024
    num_inference_steps: int = 9
    guidance_scale: float = 0.0
    seed: int = 42

@app.get("/health")
def health_check():
    return {"status": "healthy", "device": str(pipe.device)}

@app.post("/generate")
def generate_image(req: GenerateRequest):
    """
    Generate an image based on the prompt and parameters.
    Returns the image as a PNG file.
    """
    try:
        generator = torch.Generator("cuda").manual_seed(req.seed)
        
        # Generate Image
        result = pipe(
            prompt=req.prompt,
            height=req.height,
            width=req.width,
            num_inference_steps=req.num_inference_steps,
            guidance_scale=req.guidance_scale,
            generator=generator,
        )
        
        image = result.images[0]
        
        # Save image to byte buffer
        img_byte_arr = BytesIO()
        image.save(img_byte_arr, format='PNG')
        img_byte_arr.seek(0)
        
        return Response(content=img_byte_arr.getvalue(), media_type="image/png")
    
    except Exception as e:
        print(f"Error generating image: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    # Run the service
    uvicorn.run(app, host="0.0.0.0", port=6006)
