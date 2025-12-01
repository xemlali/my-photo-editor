import streamlit as st
from newspaper import Article
import requests
import base64

# --- إعدادات الصفحة ---
st.set_page_config(page_title="جالب الأخبار (بدون مصدر)", layout="centered", page_icon="🗞️")
st.title("🗞️ جالب الأخبار المباشر لووردبريس")
st.write("ضع رابط الخبر، وسأجلب النص والصورة لموقعك (مسودة) لتعدلها يدوياً.")

# --- القائمة الجانبية للإعدادات ---
with st.sidebar:
    st.header("إعدادات الاتصال")
    # جعلنا القيم فارغة لتعبئتها بنفسك
    wp_url = st.text_input("رابط الموقع (بدون / في الأخير)", "https://driouchcity.com")
    wp_user = st.text_input("اسم المستخدم")
    wp_password = st.text_input("كلمة مرور التطبيق", type="password")

# --- الدالة 1: رفع الصورة وجلب المعرف (ID) ---
def upload_image_to_wp(image_url, wp_url, wp_user, wp_password):
    try:
        # تحميل الصورة من المصدر للذاكرة
        img_response = requests.get(image_url)
        if img_response.status_code != 200:
            return None, "فشل تحميل الصورة من المصدر"
        
        image_data = img_response.content
        # محاولة استنتاج اسم للصورة
        filename = "news-image.jpg"
        if "/" in image_url:
            filename = image_url.split("/")[-1].split("?")[0]
            if not filename.endswith(('.jpg', '.png', '.jpeg', '.webp')):
                filename = "image.jpg"

        # إعداد الترويسة للرفع
        credentials = f"{wp_user}:{wp_password}"
        token = base64.b64encode(credentials.encode()).decode('utf-8')
        headers = {
            'Authorization': f'Basic {token}',
            'Content-Disposition': f'attachment; filename={filename}',
            'Content-Type': 'image/jpeg' 
        }
        
        # الرفع لووردبريس
        api_url = f"{wp_url}/wp-json/wp/v2/media"
        response = requests.post(api_url, headers=headers, data=image_data)
        
        if response.status_code == 201:
            return response.json()['id'], None
        else:
            return None, f"فشل رفع الصورة: {response.text}"
    except Exception as e:
        return None, str(e)

# --- الدالة 2: إنشاء المقال (تم تعديلها لحذف المصدر) ---
def create_post(title, content, image_id, wp_url, wp_user, wp_password):
    credentials = f"{wp_user}:{wp_password}"
    token = base64.b64encode(credentials.encode()).decode('utf-8')
    headers = {
        'Authorization': f'Basic {token}',
        'Content-Type': 'application/json'
    }
    
    # هنا التغيير: نرسل المحتوى كما هو (Content) بدون إضافة أي رابط
    post_data = {
        'title': title,
        'content': content, 
        'status': 'draft', # حالة مسودة
        'featured_media': image_id # ربط الصورة البارزة
    }
    
    api_url = f"{wp_url}/wp-json/wp/v2/posts"
    response = requests.post(api_url, headers=headers, json=post_data)
    return response

# --- الواجهة الرئيسية ---

url_input = st.text_input("🔗 ألصق رابط الخبر هنا:")

if st.button("جلب ونشر الخبر 🚀"):
    if not url_input or not wp_user or not wp_password:
        st.warning("المرجو إدخال الرابط وبيانات الدخول في القائمة الجانبية.")
    else:
        with st.spinner('جاري العمل... (قد يستغرق بضع ثوانٍ لجلب الصورة)'):
            try:
                # 1. جلب البيانات من الرابط
                article = Article(url_input)
                article.download()
                article.parse()
                
                title = article.title
                # تحويل سطور النص إلى فقرات HTML ليكون التنسيق جيداً في ووردبريس
                text = article.text.replace("\n", "<br>") 
                top_image = article.top_image
                
                st.info(f"العنوان المستخرج: {title}")
                
                # 2. معالجة الصورة
                image_id = 0
                if top_image:
                    st.image(top_image, caption="الصورة البارزة", width=300)
                    img_id, error = upload_image_to_wp(top_image, wp_url, wp_user, wp_password)
                    if img_id:
                        image_id = img_id
                    else:
                        st.warning(f"لم يتم رفع الصورة: {error}")
                
                # 3. إرسال المقال
                res = create_post(title, text, image_id, wp_url, wp_user, wp_password)
                
                if res.status_code == 201:
                    st.balloons()
                    st.success(f"✅ تم إنشاء المسودة! رقم المقال: {res.json()['id']}")
                    # عرض رابط المعاينة
                    preview_link = res.json().get('link')
                    st.markdown(f"[اضغط هنا لمعاينة وتعديل المقال في موقعك]({preview_link})")
                else:
                    st.error(f"فشل النشر. رمز الخطأ: {res.status_code}")
                    st.code(res.text)

            except Exception as e:
                st.error(f"حدث خطأ: {e}")