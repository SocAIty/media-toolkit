
from media_toolkit import ImageFile

outdir = "outdir/"
def test_img_from_url():
    url = "https://github.com/SocAIty/face2face/blob/main/test/test_imgs/test_face_1.jpg?raw=true"
    fromurl = ImageFile().from_any(url)
    fromurl.save(f"{outdir}test_face_1_1.jpg")


test_img_from_url()