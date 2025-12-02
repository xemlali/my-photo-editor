import streamlit as st
import time

# --- فحص المكتبات ---
try:
    from newspaper import Article
    import requests
    import base64
    import google.generativeai as genai
    from PIL import Image, ImageEnhance, ImageOps
    import io
    import re
    import numpy as np
except ImportError as e:
    st.error(f"❌ مكتبة ناقصة: {e}")
    st.stop()

# --- 1. إعدادات الصفحة ---
st.set_page_config(page_title="Editor Pro 11.0", layout="wide", page_icon="✒️")

# --- 2. القائمة الجانبية ---
with st.sidebar:
    st.header("1. البيانات")
    api_key = st.text_input("مفتاح Gemini API", type="password")
    wp_url = st.text_input("رابط الموقع", "https://driouchcity.com")
    wp_user = st.text_input("اسم المستخدم")
    wp_password = st.text_input("كلمة مرور التطبيق", type="password")
    
    st.divider()
    st.header("2. إعدادات المحتوى")
    target_language = st.selectbox(
        "لغة المقال:",
        ["العربية", "الإسبانية (Spanish)", "الفرنسية (French)", "الإنجليزية (English)", "الهولندية (Dutch)", "الألمانية (German)"]
    )
    
    st.divider()
    st.header("3. هندسة الصورة")
    crop_logo = st.checkbox("قص الشريط السفلي (اللوغو)", value=True)
    logo_ratio = st.slider("نسبة القص", 0.0, 0.25, 0.12, step=0.01)
    apply_mirror = st.checkbox("قلب الصورة (Mirror)", value=True)
    red_factor = st.slider("لمسة اللون الأحمر", 0.0, 0.3, 0.08, step=0.01)

# --- 3. الدوال ---

def clean_final_text(text):
    if not text: return ""
    text = text.replace("###SPLIT###", "")
    text = text.replace("###", "").replace("##", "").replace("#", "")
    text = text.replace("**", "").replace("*", "")
    text = text.replace("العنوان:", "").replace("المتن:", "")
    return text.strip()

def resize_fixed_768(image):
    target_w, target_h = 768, 432
    current_w, current_h = image.size
    target_ratio = target_w / target_h
    current_ratio = current_w / current_h
    
    if current_ratio > target_ratio:
        new_h = target_h
        # إصلاح الخطأ السابق: حساب القيمة ثم تحويلها لـ int
        calc_w = new_h * current_ratio
        new_w = int(calc_w)
        
        img = image.resize((new_w, new_h), Image.LANCZOS)
        left = (new_w - target_w) // 2
        img = img.crop((left, 0, left + target_w, target_h))
    else:
        new_w = target_w
        # إصلاح الخطأ السابق هنا أيضاً
        calc_h = new_w / current_ratio
        new_h = int(calc_h)
        
        img = image.resize((new_w, new_h), Image.LANCZOS)
        top = (new_h - target_h) // 2
        img = img.crop((0, top, target_w, top + target_h))
    return img

def process_img_pro(source, is_url, do_crop, crop_amount, do_mirror, red_val):
    try:
        if is_url:
            resp = requests.get(source, stream=True, timeout=10)
            img = Image.open(resp.raw)
        else:
            img = Image.open(source)
            
        if img.mode != 'RGB': img = img.convert('RGB')
        
        # 1. قص اللوغو
        if do_crop:
            w, h = img.size
            cut_h = h * (1 - crop_amount)
            new_h = int(cut_h)
            img = img.crop((0, 0, w, new_h))
            
        # 2. القلب
        if do_mirror:
            img = ImageOps.mirror(img)
        
        # 3. الأبعاد (768x432)
        img = resize_fixed_768(img)
        
        # 4. الألوان
        img = ImageEnhance.Color(img).enhance(1.6)
        img = ImageEnhance.Contrast(img).enhance(1.15)
        img = ImageEnhance.Sharpness(img).enhance(1.3)
        
        # 5. الطبقة الحمراء
        if red_val > 0:
            overlay = Image.new('RGB', img.size, (180, 20, 20))
            img = Image.blend(img, overlay, alpha=red_val)
        
        buf = io.BytesIO()
        img.save(buf, format='JPEG', quality=95)
        return buf.getvalue()
    except Exception as e:
        return None

def ai_rewrite_pro(txt, key, lang):
    try:
        genai.configure(api_key=key)
        model = genai.GenerativeModel('gemini-2.0-flash')
        
        # --- البرومبت "رئيس التحرير" (كما طلبت بالضبط) ---
        prompt = f"""
        **الدور:**
        تقمص دور "محرر ديسك" (Chief Editor) مخضرم في صحيفة كبرى.
        
        **المهمة:**
        أعد صياغة وترجمة النص التالي إلى اللغة: {lang}.

        **التعليمات الصارمة (خط أحمر):**
        1. **الفاصل:** استخدم ###SPLIT### للفصل بين العنوان والمقال.
        2. **الهيكلة (أهم شرط):**
           - قسم المقال إلى **4 فقرات على الأقل** (Minimum 4 paragraphs).
           - حجم الفقرة: متوسط ودسم (5-7 أسطر).
           - ممنوع كتابة النص ككتلة واحدة.
        3. **الأسلوب (Human Touch):**
           - أسلوب صحفي بشري 100%.
           - تجنب كليشيهات الذكاء الاصطناعي (مما لا شك فيه، الجدير بالذكر، يلعب دوراً محورياً...).
           - ابدأ بمقدمة مباشرة (Lead) تجيب عن الأسئلة: من؟ ماذا؟ أين؟ متى؟.

        **النص الأصلي:**
        {txt[:12000]}
        """
        resp = model.generate_content(prompt)
        return resp.text
    except Exception as e:
        return f"Error: {e}"

def wp_upload_clean(img_bytes, title, content, url, user, pwd):
    creds = f"{user}:{pwd}"
    token = base64.b64encode(creds.encode()).decode('utf-8')
    head = {'Authorization': f'Basic {token}'}
    
    mid = 0
    if img_bytes:
        h_img = head.copy()
        h_img.update({
            'Content-Disposition': 'attachment; filename=news.jpg', 
            'Content-Type': 'image/jpeg'
        })
        try:
            r = requests.post(f"{url}/wp-json/wp/v2/media", headers=h_img, data=img_bytes)
            if r.status_code == 201: mid = r.json()['id']
        except: pass

    final_body = content

    h_post = head.copy()
    h_post['Content-Type'] = 'application/json'
    data = {
        'title': title, 
        'content': final_body, 
        'status': 'draft', 
        'featured_media': mid
    }
    return requests.post(f"{url}/wp-json/wp/v2/posts", headers=h_post, json=data)

def wp_upload_image_only(img_bytes, url, user, pwd):
    creds = f"{user}:{pwd}"
    token = base64.b64encode(creds.encode()).decode('utf-8')
    head = {'Authorization': f'Basic {token}'}
    
    h_img = head.copy()
    fname = f"processed-img-{int(time.time())}.jpg"
    h_img.update({
        'Content-Disposition': f'attachment; filename={fname}', 
        'Content-Type': 'image/jpeg'
    })
    
    return requests.post(f"{url}/wp-json/wp/v2/media", headers=h_img, data=img_bytes)

# --- 4. الواجهة والتشغيل ---
st.title("✒️ المحرر (النسخة النهائية 11.0)")

tab1, tab2, tab3 = st.tabs(["🔗 رابط مقال", "📝 مقال يدوي", "🖼️ صورة فقط"])

mode = None
link_val = ""
file_val = None
text_val = ""
img_input_only = None

# === التبويب 1 ===
with tab1:
    link_val = st.text_input("رابط الخبر:")
    if st.button("🚀 معالجة (رابط)"): mode = "link"

# === التبويب 2 ===
with tab2:
    file_val = st.file_uploader("الصورة", key="man_img")
    text_val = st.text_area("النص", height=150)
    if st.button("🚀 معالجة (يدوي)"): mode = "manual"

# === التبويب 3 ===
with tab3:
    img_choice = st.radio("المصدر:", ["رفع ملف", "رابط مباشر"], horizontal=True)
    if img_choice == "رفع ملف":
        img_input_only = st.file_uploader("اختر الصورة", key="img_only_file")
    else:
        img_input_only = st.text_input("رابط الصورة:", key="img_only_url")
    if st.button("🎨 رفع الصورة فقط"): mode = "image_only"

# --- التنفيذ ---
if mode:
    if not api_key or not wp_password:
        st.error("⚠️ أدخل البيانات في القائمة الجانبية!")
    else:
        st.divider()
        status = st.container()
        
        # >>> معالجة صورة فقط <<<
        if mode == "image_only":
            if not img_input_only:
                st.error("اختر صورة أولاً!")
            else:
                status.info("جاري المعالجة... ⏳")
                is_url_mode = True if isinstance(img_input_only, str) else False
                
                final_img = process_img_pro(
                    img_input_only, is_url_mode, crop_logo, logo_ratio, apply_mirror, red_factor
                )
                
                if final_img:
                    st.image(final_img, caption="الصورة النهائية", width=400)
                    status.info("جاري الرفع...")
                    res = wp_upload_image_only(final_img, wp_url, wp_user, wp_password)
                    if res.status_code == 201:
                        img_link = res.json()['source_url']
                        st.balloons()
                        st.success("✅ تم الرفع!")
                        st.text_input("رابط الصورة:", img_link)
                    else:
                        st.error(f"فشل الرفع: {res.text}")

        # >>> معالجة مقال كامل <<<
        else:
            status.info("جاري العمل... ⏳")
            try:
                target_txt = ""
                target_img = None
                is_url = False

                if mode == "link":
                    art = Article(link_val)
                    art.download()
                    art.parse()
                    target_txt = art.text
                    target_img = art.top_image
                    is_url = True
                else:
                    target_txt = text_val
                    target_img = file_val

                # 1. الصورة
                status.write("🎨 هندسة الصورة...")
                final_img = None
                if target_img:
                    final_img = process_img_pro(
                        target_img, is_url, crop_logo, logo_ratio, apply_mirror, red_factor
                    )
                    if final_img:
                        st.image(final_img, caption="الصورة البارزة", width=400)

                # 2. النص
                status.write(f"✍️ الصياغة ({target_language})...")
                raw_ai = ai_rewrite_pro(target_txt, api_key, target_language)
                
                if "Error" in raw_ai:
                    st.error(raw_ai)
                else:
                    tit = ""
                    body = ""
                    if "###SPLIT###" in raw_ai:
                        parts = raw_ai.split("###SPLIT###")
                        tit = parts[0]
                        body = parts