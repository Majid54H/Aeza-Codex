(function () {
    var script = document.currentScript;
    if (!script || !script.src) return;
    var origin = new URL(script.src).origin;
    var width = script.getAttribute("data-width") || "380px";
    var height = script.getAttribute("data-height") || "640px";
    var iframe = document.createElement("iframe");
    iframe.src = origin + "/chat?embed=1";
    iframe.title = "Chat";
    iframe.setAttribute("loading", "lazy");
    iframe.style.cssText =
        "width:" + width + ";height:" + height + ";max-width:100%;border:0;border-radius:16px;display:block;";
    script.parentNode.insertBefore(iframe, script);
})();
