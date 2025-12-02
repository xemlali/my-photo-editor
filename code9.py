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
st.set_page_config(page_title="Editor Pro 8.0", layout="wide", page_icon="🎨")

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
        new_w = int(new_h * current_ratio)
        img = image.resize((new_w, new_h), Image.LANCZOS)
        left = (new_w - target_w) // 2
        img = img.crop((left, 0, left + target_w, target_h))
    else:
        new_w = target_w
        new_h = int(new_w / current_ratio)
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
            new_h = int(h * (1 - crop_amount))
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
        
        prompt = f"""
        **الدور:**
        تقمص دور "محرر ديسك" (Chief Editor) مخضرم.
        **المهمة:**
        أعد صياغة وترجمة النص التالي ليكون جاهزاً للنشر باللغة: {lang}.

        **التعليمات الصارمة:**
        1. **الفاصل الإجباري:** افصل بين العنوان والمقال بهذا الرمز: ###SPLIT###
        2. **الأسلوب:** بشري 100%، لغة صحفية بيضاء وسلسة. ابتعد عن "مما لا شك فيه"، "الجدير بالذكر".
        3. **الهيكل:** عنوان سطر واحد جذاب (بدون رموز). مقدمة مباشرة. فقرات قصيرة.

        **النص الأصلي:**
        {txt[:12000]}
        """
        resp = model.generate_content(prompt)
        return resp.text
    except Exception as e:
        return f"Error: {e}"

def wp_upload_clean(img_bytes, title, content, url, user, pwd):
    """دالة رفع المقال (بدون صور إضافية أو فيديو)"""
    creds = f"{user}:{pwd}"
    token = base64.b64encode(creds.encode()).decode('utf-8')
    head = {'Authorization': f'Basic {token}'}
    
    mid = 0
    if img_bytes:
        h_img = head.copy()
        h_img.update({'Content-Disposition': 'attachment; filename=news.jpg', 'Content-Type': 'image/jpeg'})
        try:
            r = requests.post(f"{url}/wp-json/wp/v2/media", headers=h_img, data=img_bytes)
            if r.status_code == 201: mid = r.json()['id']
        except: pass

    # هنا التغيير: نرسل المحتوى فقط دون أي إضافات
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
    """دالة خاصة لرفع الصورة فقط لمكتبة الوسائط"""
    creds = f"{user}:{pwd}"
    token = base64.b64encode(creds.encode()).decode('utf-8')
    head = {'Authorization': f'Basic {token}'}
    
    h_img = head.copy()
    # اسم ملف عشوائي لتفادي التكرار
    fname = f"processed-img-{int(time.time())}.jpg"
    h_img.update({'Content-Disposition': f'attachment; filename={fname}', 'Content-Type': 'image/jpeg'})
    
    return requests.post(f"{url}/wp-json/wp/v2/media", headers=h_img, data=img_bytes)

# --- 4. الواجهة والتشغيل ---
st.title("🎨 المحرر الشامل (Editor Pro 8.0)")

# إنشاء 3 تبويبات
tab1, tab2, tab3 = st.tabs(["🔗 رابط مقال", "📝 مقال يدوي", "🖼️ تعديل صورة فقط"])

mode = None
link_val = ""
file_val = None
text_val = ""
img_only_source = None # للصورة المنفردة

# === التبويب 1: رابط مقال ===
with tab1:
    link_val = st.text_input("رابط الخبر الأصلي:")
    if st.button("🚀 معالجة المقال (رابط)"): mode = "link"

# === التبويب 2: مقال يدوي ===
with tab2:
    file_val = st.file_uploader("الصورة البارزة", key="manual_img")
    text_val = st.text_area("نص الخبر", height=150)
    if st.button("🚀 معالجة المقال (يدوي)"): mode = "manual"

# === التبويب 3: تعديل صورة فقط ===
with tab3:
    st.info("هذه الخدمة تقوم بمعالجة الصورة ورفعها لمكتبة الوسائط دون إنشاء مقال.")
    img_choice = st.radio("مصدر الصورة:", ["رفع ملف", "رابط مباشر"])
    
    img_input_only = None
    if img_choice == "رفع ملف":
        img_input_only = st.file_uploader("اختر الصورة", key="img_only_file")
    else:
        img_input_only = st.text_input("ضع رابط الصورة:", key="img_only_url")
        
    if st.button("🎨 معالجة ورفع الصورة فقط"): mode = "image_only"

# --- منطقة التنفيذ ---
if mode:
    if not api_key or not wp_password:
        st.error("⚠️ أدخل البيانات في القائمة الجانبية!")
    else:
        st.divider()
        status = st.container()
        
        # >>> مسار: معالجة صورة فقط <<<
        if mode == "image_only":
            if not img_input_only:
                st.error("المرجو اختيار صورة!")
            else:
                status.info("جاري معالجة الصورة... ⏳")
                is_url_mode = True if isinstance(img_input_only, str) else False
                
                final_img = process_img_pro(
                    img_input_only, is_url_mode, crop_logo, logo_ratio, apply_mirror, red_factor
                )
                
                if final_img:
                    st.image(final_img, caption="الصورة النهائية (768x432)", width=400)
                    status.info("جاري الرفع لمكتبة الوسائط...")
                    
                    res = wp_upload_image_only(final_img, wp_url, wp_user, wp_password)
                    if res.status_code == 201:
                        img_link = res.json()['source_url']
                        st.balloons()
                        st.success("✅ تم الرفع بنجاح!")
                        st.text_input("رابط الصورة المباشر:", img_link)
                    else:
                        st.error(f"فشل الرفع: {res.text}")
                else:
                    st.error("فشلت معالجة الصورة.")

        # >>> مسار: معالجة مقال كامل (رابط أو يدوي) <<<
        else:
            status.info("جاري معالجة المقال... ⏳")
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
                        body = parts[1]
                    else:
                        lines = raw_ai.split('\n')
                        tit = lines[0]
                        body = "\n".join(lines[1:])
                    
                    tit = clean_final_text(tit)
                    body = clean_final_text(body)

                    st.success(f"📌 {tit}")
                    st.markdown(body)

                    # 3. النشر
                    status.write("🚀 الرفع...")
                    # استخدام دالة الرفع النظيفة (بدون صور إضافية)
                    res = wp_upload_clean(
                        final_img, tit, body, wp_url, wp_user, wp_password
                    )
                    
                    if res.status_code == 201:
                        lnk = res.json()['link']
                        st.balloons()
                        st.success(f"تم النشر! [رابط المعاينة]({lnk})")
                    else:
                        st.error(f"خطأ: {res.text}")

            except Exception as e:
                st.error(f"خطأ: {e}")