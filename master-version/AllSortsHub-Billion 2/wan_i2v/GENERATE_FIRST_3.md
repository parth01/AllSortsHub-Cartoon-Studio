# Generate Wan 2.2 clips — first 3 shots

This is the first real animation test for Episode 1. The GitHub workflow cannot create Wan video by itself; generate the clips in ComfyUI on a GPU machine, then put the resulting MP4 files in `wan_i2v/generated/`.

## Recommended ComfyUI setup

Use the official ComfyUI Wan 2.2 I2V workflow:

**Workflow → Browse Templates → Video → Wan2.2 14B I2V**

If the GPU cannot comfortably run the 14B workflow, use the official 5B Wan2.2 workflow/quantized setup instead. Do not commit model weights to this repository.

## Episode settings

- Output size: **832 × 480**
- Generation FPS: **16**
- Generate about **5 seconds per pass**
- Use the matching storyboard JPG/PNG as the I2V input image
- Use the motion prompt from `prompts.txt`
- Keep the same character appearance, clothing, background, and 2D cel-shaded style from the source storyboard
- Do not add text, logos, watermarks, extra people, or new props

## Shot 01 — 9 seconds

Source image:

`../01_storyboard/shot_01.jpg`

Prompt:

`Ravi sits at his computer and notices an enormous bank balance on the monitor. His eyes widen in shock, he leans closer and blinks, then pulls back in disbelief. One hand slowly moves toward the keyboard while the monitor glow illuminates his face. Subtle natural 2D cartoon body motion, expressive eyes and eyebrows, slight camera push-in, clean animation, preserve the exact character design and room.`

Generate the first ~5 seconds as:

`generated/shot_01a.mp4`

Then use the **last frame of shot_01a as the starting image** for the continuation and generate another ~5 seconds using the same prompt. Save it as:

`generated/shot_01b.mp4`

The assembler will concatenate the two clips and trim the result to the required 9 seconds.

## Shot 02 — 10 seconds

Source image:

`../01_storyboard/shot_02.jpg`

Prompt:

`Ravi points excitedly at the computer screen and looks toward Max. Max turns toward Ravi and adjusts his glasses, reacting with confusion. Ravi gestures between the screen and Max while Max studies the situation. Natural conversational 2D cartoon motion, expressive faces, subtle hand gestures, slight camera movement, preserve the exact character designs, clothing, room, and background.`

Generate:

`generated/shot_02a.mp4`

Then continue from the final frame:

`generated/shot_02b.mp4`

## Shot 03 — 5 seconds

Source image:

`../01_storyboard/shot_03.jpg`

Prompt:

`Close reaction shot of Ravi changing from confusion to excited disbelief. His eyebrows rise, his mouth opens, he glances toward the monitor and then toward Max. A subtle cinematic push-in emphasizes his reaction. Natural expressive 2D cel-shaded cartoon animation, preserve the exact face, hair, hoodie, room, colors, and background.`

Generate one clip:

`generated/shot_03.mp4`

## Before uploading to GitHub

Check that these files exist:

```text
generated/
├── shot_01a.mp4
├── shot_01b.mp4
├── shot_02a.mp4
├── shot_02b.mp4
└── shot_03.mp4
```

For each file, make sure the video opens and contains actual motion. The clips should be silent; Episode assembly adds the existing dialogue, music, SFX, and captions later.

## Test the pipeline

Once those five MP4 files are in `wan_i2v/generated/`, the GitHub Actions workflow can be updated/run in a small 3-shot test mode before generating all 17 shots.

Do **not** run the full episode workflow yet. First verify these three shots visually and adjust the prompts/workflow if Ravi or Max changes appearance between frames.
