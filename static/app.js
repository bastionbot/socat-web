async function reloadPartials() {
    const [treeRes, listRes] = await Promise.all([
        fetch("/partials/process_tree"),
        fetch("/partials/tunnel_list")
    ]);
    document.getElementById("process-tree").innerHTML = await treeRes.text();
    document.getElementById("tunnel-list").innerHTML = await listRes.text();
}

function setupForms() {
    document.body.addEventListener("submit", async (e) => {
        if (e.target.matches("form.ajax")) {
            e.preventDefault();
            const form = e.target;
            await fetch(form.action, {
                method: form.method,
                body: new FormData(form)
            });
            await reloadPartials();
        }
    });
}

document.addEventListener("DOMContentLoaded", () => {
    setupForms();
    setInterval(reloadPartials, 1000);
});
