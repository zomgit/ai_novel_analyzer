/**
 * table-resize.js - 表格列宽拖拽调整（无依赖）
 *
 * 用法：makeTableResizable(tableElement)
 * 要求：表格使用 <colgroup> 定义列（支持初始宽度），table 需设置
 *       table-layout: fixed，th 需 position: relative。
 */
function makeTableResizable(table) {
    if (!table || table.dataset.resizable) return;
    table.dataset.resizable = 'true';

    const colgroup = table.querySelector('colgroup');
    if (!colgroup) return;

    const cols = Array.from(colgroup.querySelectorAll('col'));
    const ths = Array.from(table.querySelectorAll('thead th'));

    // 列数与表头数量不匹配时不启用（避免错位）
    if (cols.length !== ths.length) return;

    let dragCol = null;
    let startX = 0;
    let startWidth = 0;

    function onMouseMove(e) {
        const delta = e.clientX - startX;
        const width = Math.max(60, startWidth + delta); // 最小列宽 60px
        cols[dragCol].style.width = width + 'px';
    }

    function onMouseUp() {
        document.removeEventListener('mousemove', onMouseMove);
        document.removeEventListener('mouseup', onMouseUp);
        document.body.style.cursor = '';
        document.body.style.userSelect = '';
        dragCol = null;
    }

    ths.forEach((th, i) => {
        // 最后一列不添加拖拽手柄（拉伸到行尾）
        if (i === ths.length - 1) return;

        const grip = document.createElement('div');
        grip.className = 'col-resizer';
        grip.title = '拖拽调整列宽';
        th.appendChild(grip);

        grip.addEventListener('mousedown', (e) => {
            e.preventDefault();
            e.stopPropagation();
            dragCol = i;
            startX = e.clientX;
            startWidth = cols[i].offsetWidth;
            document.body.style.cursor = 'col-resize';
            document.body.style.userSelect = 'none';
            document.addEventListener('mousemove', onMouseMove);
            document.addEventListener('mouseup', onMouseUp);
        });
    });
}
