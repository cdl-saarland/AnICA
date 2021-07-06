
var curr_highlighted = null;

function clickHandler(ident, target_url) {
    if (curr_highlighted != ident) {
        if (curr_highlighted != null) {
            document.getElementById(curr_highlighted).style.backgroundColor = null;
        }
        curr_highlighted = ident;
        const elem = document.getElementById(curr_highlighted)
        const color_str = window.getComputedStyle(elem).borderColor
        // this is a bit of a hack to make the color transparent
        elem.style.backgroundColor = color_str.replace("rgb", "rgba").replace(")", ", 0.2)")
    }
    document.getElementById("target").innerText = target_url;
}

