from PIL import Image, ImageDraw, ImageFont

def make_icon(size, path):
    img = Image.new('RGBA', (size, size), (0,0,0,0))
    draw = ImageDraw.Draw(img)
    m = size//8
    draw.rounded_rectangle([m,m,size-m,size-m], radius=size//5, fill=(124,58,237,255))
    try:
        font = ImageFont.truetype('C:/Windows/Fonts/arialbd.ttf', int(size*0.55))
    except:
        font = ImageFont.load_default()
    bbox = draw.textbbox((0,0),'Z',font=font)
    x=(size-(bbox[2]-bbox[0]))//2-bbox[0]
    y=(size-(bbox[3]-bbox[1]))//2-bbox[1]
    draw.text((x,y),'Z',fill=(255,255,255,255),font=font)
    img.save(path)
    print('Created', path)

make_icon(16,  'zerify-extension/icon16.png')
make_icon(48,  'zerify-extension/icon48.png')
make_icon(128, 'zerify-extension/icon128.png')