import streamlit as st
import numpy as np
from PIL import Image
from sklearn.cluster import KMeans
import colorsys

# ==========================================
# 1. 核心逻辑函数
# ==========================================

def hex_to_rgb(hex_code):
    h = hex_code.lstrip('#')
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

def rgb_to_hex(rgb):
    return '#{:02x}{:02x}{:02x}'.format(*rgb)

def extract_colors_kmeans(image, n_colors=7, ignore_dull=False):
    """
    使用 K-Means 聚类算法从图片中提取主色调
    修复了 numpy 报错，并增加了智能过滤
    """
    # 缩放图片以提高计算速度
    img_small = image.resize((150, 150))
    ar = np.asarray(img_small)
    shape = ar.shape
    
    # 去除 Alpha 通道
    if len(shape) == 3 and shape[2] > 3:
        ar = ar[:, :, :3]
    
    # 修复 numpy 报错：使用 -1 自动计算维度
    ar = ar.reshape(-1, 3)
    
    # 智能过滤：如果开启，先剔除极度灰暗或过白的像素 (简单的预处理)
    if ignore_dull:
        # 转 HSV 判断饱和度(S)和亮度(V)
        # 这里用简化的逻辑：RGB方差太小说明是灰色
        std_dev = np.std(ar, axis=1)
        # 保留色彩差异够大的像素 (阈值可调，设为10)
        ar = ar[std_dev > 10]
        if len(ar) < n_colors: # 如果过滤太狠，就回退
            ar = np.asarray(img_small).reshape(-1, 3)

    # 聚类
    if len(ar) > n_colors:
        kmeans = KMeans(n_clusters=n_colors, n_init=5, max_iter=200)
        kmeans.fit(ar)
        colors = kmeans.cluster_centers_
    else:
        colors = ar[:n_colors]
    
    # 转为 Hex 列表返回
    hex_colors = [rgb_to_hex(tuple(map(int, c))) for c in colors]
    return hex_colors

def auto_sort_colors(hex_colors, method):
    """根据规则自动排序"""
    rgb_colors = [hex_to_rgb(c) for c in hex_colors]
    
    if method == "亮度 (暗 -> 亮)":
        rgb_sorted = sorted(rgb_colors, key=lambda c: c[0]*0.299 + c[1]*0.587 + c[2]*0.114)
    elif method == "亮度 (亮 -> 暗)":
        rgb_sorted = sorted(rgb_colors, key=lambda c: c[0]*0.299 + c[1]*0.587 + c[2]*0.114, reverse=True)
    elif method == "色相 (光谱顺序)":
        rgb_sorted = sorted(rgb_colors, key=lambda c: colorsys.rgb_to_hsv(c[0]/255, c[1]/255, c[2]/255)[0])
    else:
        return hex_colors # 不排序
        
    return [rgb_to_hex(c) for c in rgb_sorted]

def generate_clr_content(hex_colors):
    content = ""
    for idx, hex_code in enumerate(hex_colors):
        r, g, b = hex_to_rgb(hex_code)
        content += f"{idx + 1} {r} {g} {b}\n"
    return content

# ==========================================
# 2. 状态管理 (实现删除/移动的关键)
# ==========================================

def init_session():
    if 'palette' not in st.session_state:
        st.session_state.palette = []
    if 'img_id' not in st.session_state:
        st.session_state.img_id = None

# 回调：删除颜色
def delete_color(index):
    if 0 <= index < len(st.session_state.palette):
        st.session_state.palette.pop(index)

# 回调：左移颜色
def move_left(index):
    if index > 0:
        lst = st.session_state.palette
        lst[index], lst[index-1] = lst[index-1], lst[index]

# 回调：右移颜色
def move_right(index):
    if index < len(st.session_state.palette) - 1:
        lst = st.session_state.palette
        lst[index], lst[index+1] = lst[index+1], lst[index]

# 回调：手动更新颜色值
def update_color_value(index, new_color):
    st.session_state.palette[index] = new_color

# ==========================================
# 3. 页面布局
# ==========================================

st.set_page_config(page_title="GIS Gradient Pro", page_icon="🎨", layout="wide")
init_session()

st.markdown("""
<style>
    .gradient-bar {
        width: 100%; height: 60px; border-radius: 8px; margin: 20px 0;
        border: 1px solid #ddd; box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .control-btn { padding: 0px 5px !important; }
</style>
""", unsafe_allow_html=True)

st.title("🎨 图片主题色提取 & 智能编辑器")
st.markdown("上传图片 -> 智能提取 -> **手动拖拽/删除/微调** -> 下载 GIS 色带")

# --- 侧边栏：提取设置 ---
with st.sidebar:
    st.header("1. 提取设置")
    uploaded_file = st.file_uploader("上传图片", type=['jpg', 'jpeg', 'png'])
    
    n_colors = st.slider("提取数量", 3, 12, 7)
    ignore_dull = st.checkbox("智能过滤背景 (去除灰/黑/白)", value=True, help="尝试忽略大面积的无聊背景色，只保留鲜艳的主题色")
    
    extract_btn = st.button("🚀 开始提取 / 重置", type="primary", use_container_width=True)
    
    st.divider()
    st.header("2. 自动排序 (可选)")
    sort_mode = st.selectbox("一键重排", ["不排序 (手动调整)", "亮度 (暗 -> 亮)", "亮度 (亮 -> 暗)", "色相 (光谱顺序)"])
    if st.button("应用排序"):
        if st.session_state.palette:
            st.session_state.palette = auto_sort_colors(st.session_state.palette, sort_mode)
            st.rerun()

    st.divider()
    st.info("💡 提示：提取后，可以在右侧直接点击色块修改颜色，或使用下方按钮调整顺序。")

# --- 主逻辑 ---

# 1. 处理图片提取
if uploaded_file:
    # 检查是否是新图片或点击了提取按钮
    file_id = uploaded_file.file_id if hasattr(uploaded_file, 'file_id') else uploaded_file.name
    
    if extract_btn or st.session_state.img_id != file_id:
        image = Image.open(uploaded_file)
        with st.spinner("正在提取主题色..."):
            new_colors = extract_colors_kmeans(image, n_colors, ignore_dull)
            # 初始默认按亮度排序，体验更好
            st.session_state.palette = auto_sort_colors(new_colors, "亮度 (暗 -> 亮)")
            st.session_state.img_id = file_id

    # 显示原图 (限制高度，节省空间)
    with st.expander("查看原图", expanded=False):
        st.image(uploaded_file, width=400)

# 2. 核心交互区
if st.session_state.palette:
    st.header("3. 色带编辑器")
    
    # 实时预览条
    current_colors = st.session_state.palette
    if len(current_colors) > 1:
        css = f"linear-gradient(to right, {', '.join(current_colors)})"
        st.markdown(f'<div class="gradient-bar" style="background: {css};"></div>', unsafe_allow_html=True)
    else:
        st.warning("色带至少需要 2 个颜色")

    # 编辑网格
    # 动态计算列数，每行显示 6 个
    cols_per_row = 6
    rows = [st.session_state.palette[i:i + cols_per_row] for i in range(0, len(st.session_state.palette), cols_per_row)]
    
    global_idx = 0
    for row in rows:
        cols = st.columns(cols_per_row)
        for idx, color in enumerate(row):
            with cols[idx]:
                # 1. 颜色选择器 (兼具展示和修改功能)
                new_col = st.color_picker(
                    f"色点 {global_idx+1}", 
                    value=color, 
                    key=f"cp_{global_idx}",
                    label_visibility="collapsed"
                )
                
                # 如果用户修改了颜色选择器，更新状态
                if new_col != color:
                    update_color_value(global_idx, new_col)
                    st.rerun()

                # 2. 控制按钮组
                b1, b2, b3 = st.columns([1, 1, 1])
                with b1:
                    # 左移
                    if global_idx > 0:
                        st.button("⬅️", key=f"l_{global_idx}", on_click=move_left, args=(global_idx,), help="左移")
                    else:
                        st.write("") # 占位
                with b2:
                    # 删除
                    st.button("❌", key=f"d_{global_idx}", on_click=delete_color, args=(global_idx,), help="删除此颜色")
                with b3:
                    # 右移
                    if global_idx < len(st.session_state.palette) - 1:
                        st.button("➡️", key=f"r_{global_idx}", on_click=move_right, args=(global_idx,), help="右移")
            
            global_idx += 1

    st.divider()

    # 4. 下载区
    st.header("4. 导出结果")
    c1, c2 = st.columns(2)
    
    filename = "extracted_palette"
    if uploaded_file:
        filename = uploaded_file.name.split('.')[0]

    with c1:
        # 下载 CLR
        clr_data = generate_clr_content(st.session_state.palette)
        st.download_button(
            label="📄 下载 ArcGIS (.clr)",
            data=clr_data,
            file_name=f"{filename}.clr",
            mime="text/plain",
            type="primary",
            use_container_width=True
        )

    with c2:
        # 下载 JSON
        json_data = [{
            "name": filename,
            "category": "Extracted",
            "tags": ["User Image"],
            "colors": st.session_state.palette
        }]
        st.download_button(
            label="📦 下载 JSON (用于备份)",
            data=json.dumps(json_data, indent=2),
            file_name=f"{filename}.json",
            mime="application/json",
            use_container_width=True
        )

else:
    st.info("👈 请在左侧上传图片开始提取")
