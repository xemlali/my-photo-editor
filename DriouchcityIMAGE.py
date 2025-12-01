import streamlit as st
from PIL import Image, ImageOps, ImageEnhance
import io
import datetime
import random
import requests
import base64
import numpy as np

# --- إعدادات الصفحة ---
st.set_page_config(page_title="DriouchCity Editor", layout="centered")
st.title("🎬 محرر الصور (DriouchCity)")

# --- دوال المعالجة (نفس الدوال السابقة) ---

def resize_and_crop_center(image: Image.Image, target_size: tuple) -> Image.Image:
    target_width, target_height = target_size
    width_ratio = target_width / image.width
    height_ratio = target_height / image.height
    scale_factor = max(width_ratio, height_ratio)
    new_width = int(image.width * scale_factor)
    new_height = int(image.height * scale_factor)
    img_resized = image.resize((new_width, new_height), Image.LANCZOS)
    left = (new_width - target_width) / 2
    top = (new_height - target_height) / 2
    right = (new_width + target_width) / 2
    bottom = (new_height + target_height) / 2
    return img_resized.crop((left, top, right, bottom))

def create_vignette(image, corner_darkness=150):
    width, height = image.size
    x = np.linspace(-1, 1, width)
    y = np.linspace(-1, 1, height)
    X, Y = np.meshgrid(x, y)
    radius = np.sqrt(X**2 + Y**2)
    radius = radius / np.max(radius)
    alpha = 1 - radius
    alpha = np.power(alpha, 2) 
    vignette_mask = Image.fromarray((alpha * 255).astype('uint8'), mode='L')
    black_layer = Image.new('RGB', (width, height), 'black')
    final_composite = Image.composite(image, black_layer, vignette_mask)
    vignette_layer = Image.new('RGBA', (width, height), (0,0,0, corner_darkness))
    vignette_layer.putalpha(ImageOps.invert(vignette_mask).point(lambda p: p * (corner_darkness/255)))
    final_image = Image.alpha_composite(image.convert('RGBA'), vignette_layer)
    return final_image.convert('RGB')

def apply_cinematic_effect(image: Image.Image) -> Image.Image:
    # قلب الصورة أفقياً أولاً كما طلبت
    img_processed = ImageOps.mirror(image)
    
    # التباين والألوان
    enhancer_contrast = ImageEnhance.Contrast(img_processed)
    img_processed = enhancer_contrast.enhance(1.3)
    enhancer_color = ImageEnhance.Color(img_processed)
    img_processed = enhancer_color.enhance(0.8)
    enhancer_sharpness = ImageEnhance.Sharpness(img_processed)
    img_processed = enhancer_sharpness.enhance(1.2)
    
    # الفينييت
    img_processed = create_vignette(img_processed)
    return img_processed

def upload_to_wordpress(image_bytes, filename, wp_url, wp_user, wp_password):
    credentials = f"{wp_user}:{wp_password}"
    token = base64.b64encode(credentials.encode()).decode('utf-8')
    headers = {
        'Authorization': f'Basic {token}',
        'Content-Disposition': f'attachment; filename={filename}',
        'Content-Type': 'image/png'
    }
    try:
        response = requests.post(f"{wp_url}/wp-json/wp/v2/media", headers=headers, data=image_bytes)
        return response
    except Exception as e:
        return str(e)

# --- واجهة التطبيق والمنطق ---

st.sidebar.header("1. رفع الصور")
st.sidebar.info("ارفع صورة واحدة لتملأ الإطار، أو صورتين لدمجهما.")
uploaded_file1 = st.sidebar.file_uploader("الصورة الأولى (الرئيسية/يمين)", type=['jpg', 'png', 'jpeg'])
uploaded_file2 = st.sidebar.file_uploader("الصورة الثانية (يسار - اختياري)", type=['jpg', 'png', 'jpeg'])

st.sidebar.header("2. إعدادات ووردبريس")
wp_url_input = st.sidebar.text_input("رابط الموقع", "")
wp_user_input = st.sidebar.text_input("اسم المستخدم", "")
wp_password_input = st.sidebar.text_input("كلمة مرور التطبيق", type="password")

if uploaded_file1:
    st.header("النتيجة")
    
    # الأبعاد النهائية الثابتة
    FINAL_W, FINAL_H = 768, 432
    final_canvas = Image.new('RGB', (FINAL_W, FINAL_H))

    with st.spinner('جاري المعالجة...'):
        img1_org = Image.open(uploaded_file1).convert('RGB')
        
        if uploaded_file2:
            # === حالة دمج صورتين ===
            img2_org = Image.open(uploaded_file2).convert('RGB')
            
            # كل صورة تأخذ نصف العرض
            SPLIT_W = int(FINAL_W / 2) # 384
            
            # قص ومعالجة الصورة 1
            img1_ready = resize_and_crop_center(img1_org, (SPLIT_W, FINAL_H))
            img1_ready = apply_cinematic_effect(img1_ready)
            
            # قص ومعالجة الصورة 2
            img2_ready = resize_and_crop_center(img2_org, (SPLIT_W, FINAL_H))
            img2_ready = apply_cinematic_effect(img2_ready)
            
            # اللصق (الصورة 2 يسار، الصورة 1 يمين)
            final_canvas.paste(img2_ready, (0, 0))
            final_canvas.paste(img1_ready, (SPLIT_W, 0))
            
        else:
            # === حالة صورة واحدة ===
            # الصورة تملأ العرض والارتفاع كاملاً
            img1_ready = resize_and_crop_center(img1_org, (FINAL_W, FINAL_H))
            img1_ready = apply_cinematic_effect(img1_ready)
            final_canvas.paste(img1_ready, (0, 0))

        st.image(final_canvas, caption=f"المقاس: {FINAL_W}x{FINAL_H}", use_column_width=True)

        # التحضير للتحميل
        today_str = datetime.date.today().strftime("%Y%m%d")
        random_num = random.randint(10000, 99999)
        filename_str = f"driouchcity-{today_str}-{random_num}.png"
        
        buf = io.BytesIO()
        final_canvas.save(buf, format="PNG", quality=95)
        byte_im = buf.getvalue()

        c1, c2 = st.columns(2)
        c1.download_button("📥 تحميل محلي", data=byte_im, file_name=filename_str, mime="image/png")
        
        if c2.button("🚀 إرسال لووردبريس"):
            if wp_url_input and wp_user_input and wp_password_input:
                res = upload_to_wordpress(byte_im, filename_str, wp_url_input, wp_user_input, wp_password_input)
                if isinstance(res, requests.models.Response) and res.status_code == 201:
                    st.success(f"تم الرفع: {filename_str}")
                else:
                    st.error("فشل الرفع، تأكد من البيانات.")
            else:
                st.warning("أدخل بيانات الموقع أولاً.")