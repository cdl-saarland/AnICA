
table_data = [
    {"id": 1, "pretty_str": "foo\nbar", "num_insns": 2, "coverage": 0.002, "mean_interestingness": 42.0, "witness_link": "foo/bar", "witness_length": 17},
    {"id": 2, "pretty_str": "foo\nbar", "num_insns": 1, "coverage": 0.012, "mean_interestingness": 8.0, "witness_link": "foo/bar", "witness_length": 23}
];
keys = ["id", "pretty_str", "num_insns", "coverage", "mean_interestingness", "witness_length", "witness_link"];

function cmp_num(a, b) {
    return a - b;
}

const sort_funs = {
    "id": cmp_num,
    "num_insns": cmp_num,
    "coverage": cmp_num,
    "mean_interestingness": cmp_num,
    "witness_length": cmp_num
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
    var old_tbody = document.getElementById("discovery_table_body");

    const new_tbody = document.createElement("tbody");
    new_tbody.id = "discovery_table_body";

    sort_fun = sort_funs[sort_key];
    if (curr_reverse) {
        actual_sort_fun = (a, b) => sort_fun(b[sort_key], a[sort_key]);
    } else {
        actual_sort_fun = (a, b) => sort_fun(a[sort_key], b[sort_key]);
    }

    table_data.sort(actual_sort_fun);

    for (const entry of table_data) {
        const new_row = document.createElement("tr");
        for (const key of keys) {
            const new_col = document.createElement("td");
            new_col.innerHTML = entry[key];
            new_row.appendChild(new_col);
        }

        new_tbody.appendChild(new_row);
    }

    old_tbody.parentNode.replaceChild(new_tbody, old_tbody);
};


document.addEventListener("DOMContentLoaded", function(event){
    drawTable("id");
});
