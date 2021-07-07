
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

function drawConnector(src_id, dst_id) {
  const src = document.getElementById(src_id);
  const dst = document.getElementById(dst_id);
  const svg = document.getElementById("arrow_svg");
  const arrow = document.createElementNS("http://www.w3.org/2000/svg", "path");

  const src_pos = {
    x: src.offsetLeft + src.offsetWidth / 2,
    y: src.offsetTop + src.offsetHeight
  };
  const dst_pos = {
    x: dst.offsetLeft + dst.offsetWidth / 2,
    y: dst.offsetTop - 5
  };
  const d_str =
      "M " + (src_pos.x) + " " + (src_pos.y) + " " +
      "C " +
      (src_pos.x) + " " + (src_pos.y + 20) + "," +
      (dst_pos.x) + " " + (dst_pos.y - 30) + "," +
      (dst_pos.x) + " " + (dst_pos.y);
  arrow.setAttribute("d", d_str);

  svg.appendChild(arrow);
};

document.addEventListener("DOMContentLoaded", function(event){
[[ARROWS]]
});
