// Resizable columns: drag the handles next to the sidebar and the pedalboard.
// Widths are remembered per browser; double-click a handle to reset it.
(function () {
    var LIMITS = {
        sidebar: { min: 260, max: 600, prop: '--sidebar', target: '.sidebar' },
        board: { min: 380, max: 2000, prop: '--board', target: '.pedalboard' }
    };

    function storageKey(name) {
        return 'pgspark.layout.' + name;
    }

    function load(name) {
        try {
            return localStorage.getItem(storageKey(name));
        } catch (e) {
            return null;
        }
    }

    function save(name, value) {
        try {
            if (value === null) {
                localStorage.removeItem(storageKey(name));
            } else {
                localStorage.setItem(storageKey(name), value);
            }
        } catch (e) { /* storage unavailable */ }
    }

    function apply(name, px) {
        var limit = LIMITS[name];
        var width = Math.round(Math.min(limit.max, Math.max(limit.min, px)));
        document.documentElement.style.setProperty(limit.prop, width + 'px');
        return width;
    }

    // Restore saved widths as early as possible to avoid a layout jump
    Object.keys(LIMITS).forEach(function (name) {
        var saved = parseInt(load(name), 10);
        if (!isNaN(saved)) {
            apply(name, saved);
        }
    });

    document.addEventListener('DOMContentLoaded', function () {
        document.querySelectorAll('.resizer[data-resize]').forEach(function (handle) {
            var name = handle.dataset.resize;
            var limit = LIMITS[name];
            var column = limit && document.querySelector(limit.target);
            if (!column) {
                return;
            }

            handle.addEventListener('pointerdown', function (e) {
                e.preventDefault();
                handle.setPointerCapture(e.pointerId);
                handle.classList.add('dragging');
                document.body.classList.add('resizing');
                var left = column.getBoundingClientRect().left;
                var width = null;

                function move(ev) {
                    width = apply(name, ev.clientX - left);
                }

                function up() {
                    handle.removeEventListener('pointermove', move);
                    handle.removeEventListener('pointerup', up);
                    handle.removeEventListener('pointercancel', up);
                    handle.classList.remove('dragging');
                    document.body.classList.remove('resizing');
                    if (width !== null) {
                        save(name, width);
                    }
                }

                handle.addEventListener('pointermove', move);
                handle.addEventListener('pointerup', up);
                handle.addEventListener('pointercancel', up);
            });

            handle.addEventListener('dblclick', function () {
                document.documentElement.style.removeProperty(limit.prop);
                save(name, null);
            });
        });
    });
})();
