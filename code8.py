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
st.set_page_config(page_title="Chief Editor Pro 7.0", layout="wide", page_icon="🌍")

# --- 2. القائمة الجانبية ---
with st.sidebar:
    st.header("1. البيانات")
    api_key = st.text_input("مفتاح Gemini API", type="password")
    wp_url = st.text_input("رابط الموقع", "https://driouchcity.com")
    wp_user = st.text_input("اسم المستخدم")
    wp_password = st.text_input("كلمة مرور التطبيق", type="password")
    
    st.divider()
    st.header("2. إعدادات المحتوى")
    # قائمة اختيار اللغة
    target_language = st.selectbox(
        "لغة المقال النهائي:",
        ["العربية", "الإسبانية (Spanish)", "الفرنسية (French)", "الإنجليزية (English)", "الهولندية (Dutch)", "الألمانية (German)"]
    )
    
    st.divider()
    st.header("3. هندسة الصورة")
    crop_logo = st.checkbox("قص الشريط السفلي (اللوغو)", value=True)
    # استعادة المؤشر للتحكم في نسبة القص
    logo_ratio = st.slider("نسبة القص من الأسفل", 0.0, 0.25, 0.12, step=0.01)
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
        
        # 1. قص اللوغو بالنسبة المحددة
        if do_crop:
            w, h = img.size
            # استخدام المتغير crop_amount من السلايدر
            new_h = int(h * (1 - crop_amount))
            img = img.crop((0, 0, w, new_h))
            
        # 2. القلب
        if do_mirror:
            img = ImageOps.mirror(img)
        
        # 3. الأبعاد
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
        
        # البرومبت الاحترافي الجديد كما طلبته
        prompt = f"""
        **الدور:**
        تقمص دور "محرر ديسك" (Chief Editor) مخضرم في صحيفة إلكترونية كبرى، يتمتع بخبرة تزيد عن 20 عاماً في تحرير الأخبار والمقالات بأسلوب بشري سلس وجذاب.

        **المهمة:**
        أعد صياغة وترجمة النص الموجود أدناه ليتحول إلى مقال صحافي احترافي جاهز للنشر باللغة: {lang}.

        **التعليمات الصارمة:**
        1. **الفاصل الإجباري:** افصل بين العنوان والمقال بهذا الرمز حصراً: ###SPLIT###
        2. **أسلوب الكتابة (Human Touch):**
           - تجنب تماماً تراكيب الذكاء الاصطناعي (في خضم، مما لا شك فيه، الجدير بالذكر، يلعب دوراً محورياً...).
           - استخدم لغة صحافية بيضاء وسلسة.
           - نوع في طول الجمل لكسر الرتابة.
           - تجنب المبالغة في الوصف.
        3. **هيكلة المقال:**
           - العنوان: سطر واحد، جذاب، يراعي SEO، بدون رموز.
           - المقدمة: دخول مباشر (Lead).
           - الجسم: فقرات قصيرة (4-5 أسطر).
           - وزع الكلمات المفتاحية بشكل طبيعي.

        **النص الأصلي:**
        {txt[:12000]}
        """
        resp = model.generate_content(prompt)
        return resp.text
    except Exception as e:
        return f"Error: {e}"

def wp_upload_full(img_bytes, title, content, extra_imgs, vids, url, user, pwd):
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

    final_body = content
    
    # إضافة الفيديوهات (فقط إذا وجدت)
    if vids:
        # فاصل بسيط
        final_body += "<br><hr>" 
        for v in vids:
            final_body += f'\n<p>{v}</p>\n'
            
    # إضافة الصور الإضافية (فقط إذا وجدت)
    if extra_imgs:
        final_body += "<br>" # مسافة فقط بدون كلمة "صور إضافية"
        count = 0
        for img_url in extra_imgs:
            if count >= 6: break # حد أقصى 6 صور
            # فلترة الأيقونات الصغيرة
            if "logo" not in img_url.lower() and "icon" not in img_url.lower() and "avatar" not in img_url.lower():
                final_body += f'\n<img src="{img_url}" style="width:100%; margin-bottom:15px; border-radius:5px;" /><br>'
                count += 1

    h_post = head.copy()
    h_post['Content-Type'] = 'application/json'
    data = {
        'title': title, 
        'content': final_body, 
        'status': 'draft', 
        'featured_media': mid
    }
    return requests.post(f"{url}/wp-json/wp/v2/posts", headers=h_post, json=data)

# --- 4. الواجهة والتشغيل ---
st.title("🌍 المحرر الدولي (Chief Editor)")

tab1, tab2 = st.tabs(["🔗 رابط خبر", "📝 رفع يدوي"])
mode = None
link_val = ""
file_val = None
text_val = ""

with tab1:
    link_val = st.text_input("رابط الخبر الأصلي:")
    if st.button("تنفيذ الرابط"): mode = "link"

with tab2:
    file_val = st.file_uploader("الصورة")
    text_val = st.text_area("النص")
    if st.button("تنفيذ اليدوي"): mode = "manual"

if mode:
    if not api_key or not wp_password:
        st.error("⚠️ أدخل البيانات في القائمة الجانبية!")
    else:
        st.divider()
        status = st.container()
        status.info("جاري العمل... ⏳")
        
        try:
            target_txt = ""
            target_img = None
            extra_imgs = []
            extra_vids = []
            is_url = False

            if mode == "link":
                art = Article(link_val)
                art.download()
                art.parse()
                target_txt = art.text
                target_img = art.top_image
                extra_imgs = art.images
                extra_vids = art.movies
                is_url = True
            else:
                target_txt = text_val
                target_img = file_val

            # 1. الصورة (مع نسبة القص المتغيرة)
            status.write("🎨 معالجة الصورة...")
            final_img = None
            if target_img:
                final_img = process_img_pro(
                    target_img, is_url, crop_logo, logo_ratio, apply_mirror, red_factor
                )
                if final_img:
                    st.image(final_img, caption="النتيجة النهائية", width=400)

            # 2. النص (مع اللغة المختارة)
            status.write(f"✍️ الصياغة والترجمة إلى ({target_language})...")
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
                
                # تنظيف
                tit = clean_final_text(tit)
                body = clean_final_text(body)

                st.success(f"📌 {tit}")
                st.markdown(body)
                
                # تنبيه في حالة وجود وسائط
                if extra_vids: st.write(f"🎥 سيتم تضمين {len(extra_vids)} فيديو.")
                if extra_imgs: st.write(f"🖼️ سيتم تضمين صور إضافية.")

                # 3. النشر
                status.write("🚀 الرفع...")
                res = wp_upload_full(
                    final_img, tit, body, extra_imgs, extra_vids, 
                    wp_url, wp_user, wp_password
                )
                
                if res.status_code == 201:
                    lnk = res.json()['link']
                    st.balloons()
                    st.success(f"تم النشر! [رابط المعاينة]({lnk})")
                else:
                    st.error(f"خطأ: {res.text}")

        except Exception as e:
            st.error(f"خطأ: {e}")