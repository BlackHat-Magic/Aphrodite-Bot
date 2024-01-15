import json

enhance = {
    "positive": "breathtaking {prompt} . award-winning, professional, highly detailed",
    "negative": "ugly, deformed, noisy, blurry, distorted, grainy"
}
anime = {
    "positive": "anime artwork {prompt} . anime style, key visual, vibrant, studio anime,  highly detailed",
    "negative": "photo, deformed, black and white, realism, disfigured, low contrast"
}
photographic = {
    "positive": "cinematic photo {prompt} . 35mm photograph, film, bokeh, professional, 4k, highly detailed",
    "negative": "drawing, painting, crayon, sketch, graphite, impressionist, noisy, blurry, soft, deformed, ugly"
}
digital_art = {
    "positive": "concept art {prompt} . digital artwork, illustrative, painterly, matte painting, highly detailed",
    "negative": "photo, photorealistic, realism, ugly"
}
comic_book = {
    "positive": "comic {prompt} . graphic illustration, comic art, graphic novel art, vibrant, highly detailed",
    "negative": "photograph, deformed, glitch, noisy, realistic, stock photo"
}
fantasy_art = {
    "positive": "ethereal fantasy concept art of  {prompt} . magnificent, celestial, ethereal, painterly, epic, majestic, magical, fantasy art, cover art, dreamy",
    "negative": "photographic, realistic, realism, 35mm film, dslr, cropped, frame, text, deformed, glitch, noise, noisy, off-center, deformed, cross-eyed, closed eyes, bad anatomy, ugly, disfigured, sloppy, duplicate, mutated, black and white"
}
analog_film = {
    "positive": "analog film photo {prompt} . faded film, desaturated, 35mm photo, grainy, vignette, vintage, Kodachrome, Lomography, stained, highly detailed, found footage",
    "negative": "painting, drawing, illustration, glitch, deformed, mutated, cross-eyed, ugly, disfigured"
}
neonpunk = {
    "positive": "neonpunk style {prompt} . cyberpunk, vaporwave, neon, vibes, vibrant, stunningly beautiful, crisp, detailed, sleek, ultramodern, magenta highlights, dark purple shadows, high contrast, cinematic, ultra detailed, intricate, professional",
    "negative": "painting, drawing, illustration, glitch, deformed, mutated, cross-eyed, ugly, disfigured"
}
isometric = {
    "positive": "isometric style {prompt} . vibrant, beautiful, crisp, detailed, ultra detailed, intricate",
    "negative": "deformed, mutated, ugly, disfigured, blur, blurry, noise, noisy, realistic, photographic"
}
lowpoly = {
    "positive": "low-poly style {prompt} . low-poly game art, polygon mesh, jagged, blocky, wireframe edges, centered composition",
    "negative": "noisy, sloppy, messy, grainy, highly detailed, ultra textured, photo"
}
origami = {
    "positive": "origami style {prompt} . paper art, pleated paper, folded, origami art, pleats, cut and fold, centered composition",
    "negative": "noisy, sloppy, messy, grainy, highly detailed, ultra textured, photo"
}
line_art = {
    "positive": "line art drawing {prompt} . professional, sleek, modern, minimalist, graphic, line art, vector graphics",
    "negative": "anime, photorealistic, 35mm film, deformed, glitch, blurry, noisy, off-center, deformed, cross-eyed, closed eyes, bad anatomy, ugly, disfigured, mutated, realism, realistic, impressionism, expressionism, oil, acrylic"
}
craft_clay = {
    "positive": "play-doh style {prompt} . sculpture, clay art, centered composition, Claymation",
    "negative": "sloppy, messy, grainy, highly detailed, ultra textured, photo"
}
cinematic = {
    "positive": "cinematic film still {prompt} . shallow depth of field, vignette, highly detailed, high budget Hollywood movie, bokeh, cinemascope, moody, epic, gorgeous, film grain, grainy",
    "negative": "anime, cartoon, graphic, text, painting, crayon, graphite, abstract, glitch, deformed, mutated, ugly, disfigured"
}
model = {
    "positive": "professional 3d model {prompt} . octane render, highly detailed, volumetric, dramatic lighting",
    "negative": "ugly, deformed, noisy, low poly, blurry, painting"
}
pixel_art = {
    "positive": "pixel-art {prompt} . low-res, blocky, pixel art style, 8-bit graphics",
    "negative": "sloppy, messy, blurry, noisy, highly detailed, ultra textured, photo, realistic"
}
texture = {
    "positive": "texture {prompt} top down close-up",
    "negative": "ugly, deformed, noisy, blurry"
}

styles = {
    "Enhance": enhance,
    "Anime": anime,
    "Photographic": photographic,
    "Digital Art": digital_art,
    "Comic Book": comic_book,
    "Fantasy Art": fantasy_art,
    "Analog Film": analog_film,
    "Neonpunk": neonpunk,
    "Isometric": isometric,
    "Low-Poly": lowpoly,
    "Origami": origami,
    "Line Art": line_art,
    "Craft Clay": craft_clay,
    "Cinematic": cinematic,
    "3D Model": model,
    "Pixel Art": pixel_art,
    "Texture": texture
}

with open("./styles.json", "w") as f:
    json.dump(styles, f, indent=4)