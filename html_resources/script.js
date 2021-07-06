
var curr_highlighted = null;

function clickHandler(ident, target_url) {
    if (curr_highlighted != ident) {
        if (curr_highlighted != null) {
            document.getElementById(curr_highlighted).classList.remove("highlighted")
        }
        curr_highlighted = ident;
        document.getElementById(curr_highlighted).classList.add("highlighted")
    }
    document.getElementById("target").innerText = target_url;
}

