import streamlit as st
from newspaper import Article
import requests
import base64
import google.generativeai as genai
from PIL import Image, ImageEnhance, ImageOps
import io
import numpy as np

# --- 1. إعدادات الصفحة ---
st.set_page_config(page_title="المحرر الذكي 4.0", layout="wide", page_icon="🔥")

# --- 2. القائمة الجانبية ---
with st.sidebar:
    st.header("🔐 الإعدادات")
    wp_url = st.text_input("رابط الموقع", "https://driouchcity.com")
    wp_user = st.text_input("اسم المستخدم (WordPress)")
    wp_password = st.text_input("كلمة مرور التطبيق", type="password")
    st.divider()
    api_key = st.text_input("مفتاح Gemini API", type="password")
    
    st.divider()
    st.header("🎨 أدوات الصورة")
    remove_logo = st.checkbox("قص الحافة السفلية (اللوغو)", value=True)
    logo_crop_ratio = st.slider("نسبة القص", 0.0, 0.20, 0.12, step=0.01)

# --- 3. الدوال البرمجية ---

def create_red_vignette(image):
    """إضافة هالة حمراء داكنة بدلاً من السوداء"""
    if image.mode != 'RGB':
        image = image.convert('RGB')
    width, height = image.size
    x = np.linspace(-1, 1, width)
    y = np.linspace(-1, 1, height)
    X, Y = np.meshgrid(x, y)
    
    radius = np.sqrt(X**2 + Y**2)
    radius = radius / np.max(radius)
    alpha = 1 - radius
    alpha = np.power(alpha, 1.2) # تحكم في انتشار اللون
    
    mask_arr = (alpha * 255).astype('uint8')
    vignette_mask = Image.fromarray(mask_arr, mode='L')
    
    # اللون الأحمر الداكن (Dark Red) ليعطي طابعاً درامياً وليس فاقعاً
    # يمكنك تغيير الأرقام (R, G, B) لتفتيح أو تغميق الأحمر
    red_layer = Image.new('RGB', (width, height), (100, 0, 0)) 
    
    return Image.composite(image, red_layer, vignette_mask)

def process_image(image_input, should_crop, crop_ratio):
    try:
        # التعامل مع المدخلات سواء كانت رابطاً أو ملفاً مرفوعاً
        if isinstance(image_input, str): # إذا كان رابطاً
            response = requests.get(image_input, stream=True)
            img = Image.open(response.raw)
        else: # إذا كان ملفاً مرفوعاً
            img = Image.open(image_input)
        
        if img.mode in ('RGBA', 'P'):
            img = img.convert('RGB')
        
        # 1. القلب الأفقي (Mirror) - طلب جديد
        img = ImageOps.mirror(img)

        # 2. قص اللوغو
        if should_crop:
            w, h = img.size
            new_h = int(h * (1 - crop_ratio))
            img = img.crop((0, 0, w, new_h))
        
        # 3. التأثيرات (ألوان + حدة + هالة حمراء)
        img = ImageEnhance.Color(img).enhance(1.3)
        img = ImageEnhance.Contrast(img).enhance(1.2)
        img = ImageEnhance.Sharpness(img).enhance(1.3)
        img = create_red_vignette(img) # استخدام الهالة الحمراء
        
        buf = io.BytesIO()
        img.save(buf, format='JPEG', quality=95)
        return buf.getvalue()
    except Exception as e:
        st.error(f"خطأ في معالجة الصورة: {e}")
        return None

def rewrite_article_ai(text, key):
    try:
        genai.configure(api_key=key)
        model = genai.GenerativeModel('gemini-2.0-flash')
        
        prompt = f"""
        أنت صحفي خبير. أعد صياغة النص التالي ليكون مقالاً احترافياً:
        1. العنوان: سطر واحد فقط في البداية، جذاب وذكي.
        2. المحتوى: أسلوب قصصي، فقرات مترابطة، لغة قوية.
        3. تنظيف: لا تستخدم النجمات (**) نهائياً في النص.
        
        النص الأصلي:
        {text[:9000]}
        """
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Error: {e}"

def upload_to_wp(img_data, title, content, url, user, password):
    creds = f"{user}:{password}"
    token = base64.b64encode(creds.encode()).decode('utf-8')
    headers_auth = {'Authorization': f'Basic {token}'}

    # رفع الصورة
    media_id = 0
    if img_data:
        headers_img = headers_auth.copy()
        headers_img['Content-Disposition'] = 'attachment; filename=news-red-effect.jpg'
        headers_img['Content-Type'] = 'image/jpeg'
        try:
            r = requests.post(f"{url}/wp-json/wp/v2/media", headers=headers_img, data=img_data)
            if r.status_code == 201:
                media_id = r.json()['id']
        except:
            pass

    # رفع المقال
    headers_post = headers_auth.copy()
    headers_post['Content-Type'] = 'application/json'
    post_data = {
        'title': title,
        'content': content,
        'status': 'draft',
        'featured_media': media_id
    }
    return requests.post(f"{url}/wp-json/wp/v2/posts", headers=headers_post, json=post_data)

# --- 4. الواجهة الرئيسية (نظام التبويبات) ---
st.title("🔥 المحرر الصحفي (Red Edition)")
st.markdown("---")

# إنشاء التبويبات
tab1, tab2 = st.tabs(["🔗 جلب من رابط", "📝 رفع يدوي (صورة ونص)"])

# === التبويب 1: الرابط ===
with tab1:
    url_input = st.text_input("رابط الخبر:", placeholder="https://...")
    btn_link = st.button("تشغيل المعالج (رابط)", type="primary")

# === التبويب 2: الرفع اليدوي ===
with tab2:
    col_img, col_txt = st.columns([1, 2])
    with col_img:
        uploaded_img = st.file_uploader("اختر الصورة", type=['jpg', 'png', 'jpeg'])
    with col_txt:
        uploaded_txt = st.text_area("ألصق النص هنا", height=150)
    btn_manual = st.button("تشغيل المعالج (يدوي)", type="primary")

# --- 5. منطق التشغيل الموحد ---
target_text = ""
target_image = None
start_processing = False

if btn_link and url_input:
    start_processing = True
    with st.spinner("جاري جلب الرابط..."):
        try:
            art = Article(url_input)
            art.download()
            art.parse()
            target_text = art.text
            target_image = art.top_image # هذا رابط نصي
        except Exception as e:
            st.error(f"فشل الجلب: {e}")
            start_processing = False

elif btn_manual and uploaded_img and uploaded_txt:
    start_processing = True
    target_text = uploaded_txt
    target_image = uploaded_img # هذا ملف بايتس

# --- تنفيذ المعالجة ---
if start_processing:
    if not api_key or not wp_password:
        st.error("⚠️ أدخل بيانات الدخول في القائمة الجانبية.")
    else:
        with st.status("جاري تنفيذ السحر... ⏳", expanded=True) as status:
            try:
                # 1. الصورة
                status.write("🎨 معالجة الصورة (قلب + أحمر + قص)...")
                final_img_bytes = None
                if target_image:
                    final_img_bytes = process_image(target_image, remove_logo, logo_crop_ratio)
                    if final_img_bytes:
                        st.image(final_img_bytes, caption="النتيجة النهائية", width=400)
                
                # 2. النص
                status.write("🤖 إعادة الصياغة وتنظيف النص...")
                ai_res = rewrite_article_ai(target_text, api_key)
                
                if "Error" in ai_res:
                    status.update(label="خطأ AI", state="error")
                    st.error(ai_res)
                else:
                    # تنظيف النجمات (طلبك الخاص)
                    ai_res_clean = ai_res.replace("**", "")
                    
                    lines = ai_res_clean.split('\n')
                    # استخراج العنوان (أول سطر غير فارغ)
                    tit = next((l for l in lines if l.strip()), "عنوان")
                    tit = tit.strip()
                    
                    # المحتوى هو كل شيء ما عدا العنوان
                    # نستخدم فلتر لضمان عدم تكرار العنوان في المتن
                    body_lines = [l for l in lines if l.strip() and l.strip() != tit]
                    con = "\n".join(body_lines)
                    
                    st.success("تمت الصياغة:")
                    st.text_input("العنوان المستخرج", tit) # للعرض فقط
                    st.markdown(con)
                    
                    # 3. النشر
                    status.write("🚀 الإرسال للموقع...")
                    res = upload_to_wp(final_img_bytes, tit, con, wp_url, wp_user, wp_password)
                    
                    if res.status_code == 201:
                        status.update(label="✅ تم بنجاح!", state="complete", expanded=False)
                        st.balloons()
                        lnk = res.json()['link']
                        st.success(f"المقال جاهز في المسودات! [اضغط للمعاينة]({lnk})")
                    else:
                        st.error(f"خطأ ووردبريس: {res.text}")

            except Exception as e:
                st.error(f"خطأ غير متوقع: {e}")