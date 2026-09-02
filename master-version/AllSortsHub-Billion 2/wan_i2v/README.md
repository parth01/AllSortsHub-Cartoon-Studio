# Episode 1 — Wan 2.2 I2V production

This folder is the AI-animation handoff for **The Guy Who Got $1 Billion for One Day**.

## Recommended workflow

Use the official ComfyUI Wan 2.2 Image-to-Video template. ComfyUI currently provides a native **Wan 2.2 14B I2V** workflow and also a 5B video workflow. Start with the 14B I2V template when your GPU can handle it; use the 5B workflow for lower VRAM. The official ComfyUI guidance is to update ComfyUI, open **Workflow → Browse Templates → Video**, choose the Wan 2.2 image-to-video workflow, and let ComfyUI download the required models.

For this episode:

1. Use the existing storyboard image for the shot as the input image.
2. Copy the matching motion prompt from `prompts.txt`.
3. Generate a first 5-second clip.
4. For shots longer than 5 seconds, use the last frame of the first clip as the start image for the continuation and generate the remaining movement. Do not independently regenerate the same character from scratch.
5. Save the generated clips as `../04_wan_clips/shot_XXa.mp4` and, when needed, `shot_XXb.mp4`.
6. The production renderer will prefer these Wan clips over the old still-image camera animation. If no Wan clip exists, it automatically falls back to the existing storyboard renderer.

## Shot timing

The episode currently uses these target durations:

`9, 10, 5, 9, 9, 8, 9, 10, 10, 8, 10, 10, 10, 10, 10, 9, 8` seconds.

For a 5-second Wan generation, use one clip for a 5-second shot and two chained clips for the longer shots. The renderer trims the combined result to the target shot duration.

## Character consistency rules

- Preserve Ravi's messy black hair, red-orange zip hoodie, white T-shirt, dark grey joggers and chunky white sneakers.
- Preserve Max's neat dark brown hair, round black glasses, teal-blue button-up over grey T-shirt, navy jeans and brown loafers.
- Preserve the original environment, props, color palette and 2D cel-shaded cartoon style.
- Prefer subtle, physically plausible motion over large body changes.
- Do not introduce new characters unless the prompt explicitly asks for them.
- Avoid changing clothing, hairstyle, facial proportions, room layout, signs, screens or important props.

## Important

Do not commit large model files to GitHub. Commit the small prompts/manifests and the final rendered MP4s only if you deliberately want them versioned. Wan model weights should remain on the GPU machine/cloud instance.

Official references:
- ComfyUI Wan 2.2 support: https://blog.comfy.org/p/wan22-day-0-support-in-comfyui
- ComfyUI Wan workflows: https://comfy.org/workflows/model/wan/
