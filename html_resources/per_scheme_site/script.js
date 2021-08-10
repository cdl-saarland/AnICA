
table_data = [[table_data]];

keys = ["scheme", "num_discoveries"];

function cmp_num(a, b) {
    return a - b;
}

function cmp_str(a, b) {
    return a < b ? -1 : 1;
}

function cmp_num_str(a, b) {
    if (a == "inf") {
        a = Infinity;
    } else {
        a = parseFloat(a);
    }
    if (b == "inf") {
        b = Infinity;
    } else {
        b = parseFloat(b);
    }
    return a - b;
}

const sort_funs = {
    "scheme": cmp_str,
    "num_discoveries": cmp_num
};

var curr_key = null;
var curr_reverse = false;

function drawTable(sort_key) {
    if (curr_key == sort_key) {
        curr_reverse = (! curr_reverse);
    } else {
        curr_reverse = false;
    }

    curr_key = sort_key;
    var old_tbody = document.getElementById("per_scheme_table_body");

    const new_tbody = document.createElement("tbody");
    new_tbody.id = "per_scheme_table_body";

    sort_fun = sort_funs[sort_key];
    if (curr_reverse) {
        actual_sort_fun = (a, b) => sort_fun(b[sort_key], a[sort_key]);
    } else {
        actual_sort_fun = (a, b) => sort_fun(a[sort_key], b[sort_key]);
    }

    table_data.sort(actual_sort_fun);

    for (const entry of table_data) {
        const new_row = document.createElement("tr");
        new_row.className = "per_scheme_tr";
        for (const key of keys) {
            const new_col = document.createElement("td");
            new_col.className = "per_scheme_td";
            new_col.innerHTML = entry[key];
            new_row.appendChild(new_col);
        }

        new_tbody.appendChild(new_row);
    }

    old_tbody.parentNode.replaceChild(new_tbody, old_tbody);
};


document.addEventListener("DOMContentLoaded", function(event){
    drawTable("scheme");
});

