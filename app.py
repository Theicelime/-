import streamlit as st
import numpy as np
from PIL import Image
from sklearn.cluster import KMeans
import colorsys
import json
# 引入拖拽库
from streamlit_sortables import sort_items

# ==========================================
# 1. 核心逻辑
# ==========================================

def hex_to_rgb(hex_code):
    h = hex_code.lstrip('#')
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

def rgb_to_hex(rgb):
    return '#{:02x}{:02x}{:02x}'.format(*rgb)

def extract_smart_colors(image, n_colors=7, min_sat=0.1, min_val=0.1):
    """智能提取算法 (HSV过滤 + K-Means)"""
    img_small = image.resize((200, 200)) 
    ar = np.asarray(img_small)
    
    if len(ar.shape) == 3 and ar.shape[2] > 3:
        ar = ar[:, :, :3]
    
    ar = ar.reshape(-1, 3)
    
    # 随机采样以提速
    if len(ar) > 5000:
        indices = np.random.choice(len(ar), 5000, replace=False)
        sample_ar = ar[indices]
    else:
        sample_ar = ar

    valid_pixels = []
    for pixel in sample_ar:
        r, g, b = pixel
        h, s, v = colorsys.rgb_to_hsv(r/255.0, g/255.0, b/255.0)
        # 过滤灰/黑/白
        if s >= min_sat and v >= min_val:
            valid_pixels.append(pixel)
    
    if len(valid_pixels) < n_colors:
        valid_pixels = sample_ar
    
    valid_pixels = np.array(valid_pixels)

    kmeans = KMeans(n_clusters=n_colors, n_init=5, max_iter=200)
    kmeans.fit(valid_pixels)
    colors = kmeans.cluster_centers_
    
    # 转换为Hex列表
    hex_list = [rgb_to_hex(tuple(map(int, c))) for c in colors]
    
    # 默认按亮度排序，提供一个好的初始状态
    rgb_colors = [hex_to_rgb(c) for c in hex_list]
    rgb_sorted = sorted(rgb_colors, key=lambda c: c[0]*0.299 + c[1]*0.587 + c[2]*0.114)
    return [rgb_to_hex(c) for c in rgb_sorted]

def generate_clr(hex_colors):
    content = ""
    for idx, hex_code in enumerate(hex_colors):
        r, g, b = hex_to_rgb(hex_code)
        content += f"{idx + 1} {r} {g} {b}\n"
    return content

# ==========================================
# 2. 页面与交互
# ==========================================
st.set_page_config(page_title="GIS Drag & Drop Palette", page_icon="🎨", layout="wide")

# 注入 CSS 让界面更专业
st.markdown("""
<style>
    .gradient-preview {
        width: 100%; height: 80px; border-radius: 12px; margin-bottom: 20px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1); border: 2px solid #fff;
    }
    .stButton button { width: 100%; }
</style>
""", unsafe_allow_html=True)

# 初始化 Session State
if 'palette' not in st.session_state:
    st.session_state.palette = []
if 'img_key' not in st.session_state:
    st.session_state.img_key = None

st.title("🎨 GIS 拖拽式色带生成器")
st.caption("上传图片 -> 智能提取 -> **拖拽排序** -> 导出 CLR")

# --- 侧边栏 ---
with st.sidebar:
    st.header("1. 提取源")
    uploaded_file = st.file_uploader("上传图片 (电影截图/色卡)", type=['jpg', 'png', 'jpeg'])
    
    st.divider()
    n_colors = st.slider("颜色数量", 3, 12, 7)
    min_sat = st.slider("最低饱和度 (去灰)", 0.0, 1.0, 0.2)
    min_val = st.slider("最低亮度 (去黑)", 0.0, 1.0, 0.2)
    
    run_btn = st.button("🚀 提取颜色", type="primary")

# --- 逻辑处理 ---
if uploaded_file:
    # 生成唯一key防止重复计算
    current_key = f"{uploaded_file.name}_{n_colors}_{min_sat}_{min_val}"
    
    if run_btn or st.session_state.img_key != current_key:
        image = Image.open(uploaded_file)
        with st.spinner("正在提取并进行智能预排序..."):
            new_colors = extract_smart_colors(image, n_colors, min_sat, min_val)
            st.session_state.palette = new_colors
            st.session_state.img_key = current_key

    with st.expander("查看原图", expanded=False):
        st.image(uploaded_file, width=300)

# --- 主交互区 ---
if st.session_state.palette:
    
    # 1. 实时渐变预览 (放在最显眼的位置)
    st.subheader("2. 渐变预览 (实时响应拖拽)")
    css = f"linear-gradient(to right, {', '.join(st.session_state.palette)})"
    st.markdown(f'<div class="gradient-preview" style="background: {css};"></div>', unsafe_allow_html=True)

    # 2. 拖拽排序区 (核心功能)
    st.subheader("3. 拖拽排序 & 编辑")
    st.info("👇 **按住下面的色块进行拖拽排序**，松开后上方预览会自动更新。")
    
    # 使用 streamlit_sortables 实现拖拽
    # 注意：这里 items 传入的是 Hex 字符串列表
    sorted_palette = sort_items(st.session_state.palette, direction='horizontal')

    # 检测拖拽变化：如果排序结果变了，更新 session_state 并重新渲染
    if sorted_palette != st.session_state.palette:
        st.session_state.palette = sorted_palette
        st.rerun()

    # 3. 颜色微调与删除 (基于排序后的列表)
    # 显示颜色选择器，允许用户改色或删除
    cols = st.columns(len(st.session_state.palette))
    for i, color in enumerate(st.session_state.palette):
        with cols[i]:
            # 颜色选择器
            new_val = st.color_picker(f"色{i+1}", color, key=f"cp_{i}", label_visibility="collapsed")
            if new_val != color:
                st.session_state.palette[i] = new_val
                st.rerun()
            
            # 删除按钮
            if st.button("🗑️", key=f"del_{i}"):
                st.session_state.palette.pop(i)
                st.rerun()

    st.divider()

    # 4. 导出
    st.subheader("4. 导出")
    c1, c2 = st.columns(2)
    base_name = uploaded_file.name.split('.')[0]
    
    with c1:
        st.download_button(
            "⬇️ 下载 ArcGIS .clr 文件",
            data=generate_clr(st.session_state.palette),
            file_name=f"{base_name}_gradient.clr",
            mime="text/plain",
            type="primary",
            use_container_width=True
        )
    with c2:
        # 允许下载 JSON 格式，方便你添加到之前的库里
        json_data = [{"name": base_name, "category": "Extracted", "tags": ["User"], "colors": st.session_state.palette}]
        st.download_button(
            "📦 下载 JSON 备份",
            data=json.dumps(json_data, indent=2),
            file_name=f"{base_name}.json",
            use_container_width=True
        )

else:
    st.info("👈 请在左侧上传图片开始")
