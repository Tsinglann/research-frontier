// 研究前沿助手 —— GNOME Shell 扩展（最小可用实现）
//
// 设计：后端（update.py）把数据写到 @DATA_DIR@ 下的 JSON，
// 扩展只负责读文件 + 在顶栏放一个指示器 + 弹出面板展示。
// 这与 Plasma 小组件共用同一份后端数据，逻辑保持一致。
import GObject from 'gi://GObject';
import St from 'gi://St';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import Clutter from 'gi://Clutter';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as PanelMenu from 'resource:///org/gnome/shell/ui/panelMenu.js';
import * as PopupMenu from 'resource:///org/gnome/shell/ui/popupMenu.js';
import { Extension } from 'resource:///org/gnome/shell/extensions/extension.js';

const DATA_DIR = '@DATA_DIR@';

function readJson(name) {
    try {
        const f = Gio.File.new_for_path(`${DATA_DIR}/${name}.json`);
        const [, bytes] = f.load_contents(null);
        return JSON.parse(new TextDecoder().decode(bytes));
    } catch (e) {
        return null;
    }
}

const Indicator = GObject.registerClass(
class Indicator extends PanelMenu.Button {
    _init() {
        super._init(0.0, '研究前沿');
        this._label = new St.Label({
            text: '🔭',
            y_align: Clutter.ActorAlign.CENTER,
        });
        this.add_child(this._label);
        this._build();
        // 每 5 分钟重读一次产物
        this._timer = GLib.timeout_add_seconds(GLib.PRIORITY_DEFAULT, 300, () => {
            this._build();
            return GLib.SOURCE_CONTINUE;
        });
    }

    _clear() {
        this.menu.removeAll();
    }

    _add(text, style) {
        const item = new PopupMenu.PopupMenuItem(text, { reactive: false });
        if (style)
            item.label.set_style(style);
        this.menu.addMenuItem(item);
        return item;
    }

    _build() {
        this._clear();
        const brief = readJson('brief');
        const papers = readJson('papers');
        if (!brief) {
            this._add('还没有数据');
            this._add('先跑 update.py all');
            return;
        }
        const b = brief.generated_text || '-';
        this._add(`研究前沿 · ${b}`, 'font-weight:bold;');
        this._add(`入选 ${brief.picked_count || 0} 篇 / 候选 ${brief.candidate_count || 0} 篇`);

        const cl = brief.classic;
        if (cl && cl.title) {
            this.menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());
            this._add('📜 经典回顾', 'font-weight:bold;');
            this._add(`${cl.year || ''} ${cl.title}`.slice(0, 90));
            if (cl.review)
                this._add(cl.review.split('\n')[0].slice(0, 110));
        }

        if (papers && papers.papers && papers.papers.length) {
            this.menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());
            this._add('📄 入选论文', 'font-weight:bold;');
            papers.papers.slice(0, 8).forEach((p, i) => {
                const item = new PopupMenu.PopupMenuItem(
                    `${i + 1}. ${p.title}`.slice(0, 96));
                item.connect('activate', () => {
                    const url = p.pdfurl || (p.doi ? `https://doi.org/${p.doi}` : p.url);
                    if (url)
                        Gio.AppInfo.launch_default_for_uri(url, null);
                });
                this.menu.addMenuItem(item);
            });
        }

        this.menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());
        const open = new PopupMenu.PopupMenuItem('🌐 打开浏览器版');
        open.connect('activate', () => {
            const home = GLib.get_home_dir();
            const site = Gio.File.new_for_path(
                `${DATA_DIR}/../daily/site/index.html`);
            if (site.query_exists(null))
                Gio.AppInfo.launch_default_for_uri(site.get_uri(), null);
        });
        this.menu.addMenuItem(open);
    }

    destroy() {
        if (this._timer) { GLib.source_remove(this._timer); this._timer = null; }
        super.destroy();
    }
});

export default class ResearchFrontierExtension extends Extension {
    enable() {
        this._indicator = new Indicator();
        Main.panel.addToStatusArea(this.uuid, this._indicator);
    }
    disable() {
        this._indicator?.destroy();
        this._indicator = null;
    }
}
