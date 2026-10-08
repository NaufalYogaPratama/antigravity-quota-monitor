import GLib from 'gi://GLib';
import Gio from 'gi://Gio';
import St from 'gi://St';
import Clutter from 'gi://Clutter';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import { Extension } from 'resource:///org/gnome/shell/extensions/extension.js';

export default class AntigravityQuotaExtension extends Extension {
    enable() {
        this._container = null;
        this._openStateSignalId = null;
        this._refreshTimeoutId = null;
        this._activeTab = 'antigravity';
        this._cachedData = null;

        const dateMenu = Main.panel.statusArea.dateMenu;
        if (!dateMenu) {
            console.error('[AntigravityQuota] dateMenu not found in statusArea');
            return;
        }

        this._dateMenu = dateMenu;

        // Create main container box
        this._container = new St.BoxLayout({
            vertical: true,
            style_class: 'antigravity-quota-box',
            x_expand: true,
            y_expand: false,
        });

        // Insert container into the calendar column
        this._ensureWidgetInserted();

        // Listen to menu open state to refresh on open & ensure insertion
        this._openStateSignalId = this._dateMenu.menu.connect('open-state-changed', (menu, isOpen) => {
            if (isOpen) {
                this._ensureWidgetInserted();
                this._fetchAndUpdate();
            }
        });

        // Periodic background refresh every 60s
        this._refreshTimeoutId = GLib.timeout_add_seconds(GLib.PRIORITY_DEFAULT, 60, () => {
            if (this._dateMenu && this._dateMenu.menu && this._dateMenu.menu.isOpen) {
                this._fetchAndUpdate();
            }
            return GLib.SOURCE_CONTINUE;
        });

        // Initial fetch
        this._fetchAndUpdate();
    }

    _ensureWidgetInserted() {
        if (!this._container || this._container.get_parent()) {
            return; // already inserted and has a parent
        }
        this._insertWidget();
    }

    _insertWidget() {
        const dateMenu = this._dateMenu;
        let targetBox = null;

        // In GNOME Shell 46, calendar items (_clocksItem, _weatherItem, _eventsItem) are inside displayBox
        if (dateMenu._clocksItem && dateMenu._clocksItem.get_parent()) {
            targetBox = dateMenu._clocksItem.get_parent();
        } else if (dateMenu._weatherItem && dateMenu._weatherItem.get_parent()) {
            targetBox = dateMenu._weatherItem.get_parent();
        } else if (dateMenu._eventsItem && dateMenu._eventsItem.get_parent()) {
            targetBox = dateMenu._eventsItem.get_parent();
        } else if (dateMenu._calendar && dateMenu._calendar.get_parent()) {
            targetBox = dateMenu._calendar.get_parent();
        } else if (dateMenu._messageList && dateMenu._messageList._box) {
            targetBox = dateMenu._messageList._box;
        }

        if (targetBox) {
            // Find weatherItem or clocksItem to insert right below it
            const refItem = dateMenu._weatherItem || dateMenu._clocksItem;
            if (refItem && refItem.get_parent() === targetBox) {
                const children = targetBox.get_children();
                const index = children.indexOf(refItem);
                if (index >= 0) {
                    targetBox.insert_child_at_index(this._container, index + 1);
                    console.log(`[AntigravityQuota] Widget inserted at index ${index + 1}`);
                    return;
                }
            }
            targetBox.add_child(this._container);
            console.log('[AntigravityQuota] Widget added to targetBox');
        } else {
            console.error('[AntigravityQuota] Target calendar container not found');
        }
    }

    _fetchAndUpdate() {
        const scriptPath = GLib.build_filenamev([this.path, 'data_fetcher.py']);
        if (!GLib.file_test(scriptPath, GLib.FileTest.EXISTS)) {
            this._renderError('data_fetcher.py not found');
            return;
        }

        try {
            const proc = Gio.Subprocess.new(
                ['python3', scriptPath],
                Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_PIPE
            );

            proc.communicate_utf8_async(null, null, (proc, res) => {
                try {
                    const [, stdout, stderr] = proc.communicate_utf8_finish(res);
                    if (proc.get_successful()) {
                        const data = JSON.parse(stdout);
                        this._cachedData = data;
                        this._renderData(data);
                    } else {
                        console.error('[AntigravityQuota] Fetcher stderr:', stderr);
                        this._renderError('Fetch failed');
                    }
                } catch (e) {
                    console.error('[AntigravityQuota] JSON parse error:', e);
                    this._renderError('Parse error');
                }
            });
        } catch (e) {
            console.error('[AntigravityQuota] Subprocess launch error:', e);
            this._renderError('Subprocess error');
        }
    }

    _switchTab(tabName) {
        if (this._activeTab === tabName) return;
        this._activeTab = tabName;
        if (this._cachedData) {
            this._renderData(this._cachedData);
        }
    }

    _renderError(message) {
        if (!this._container) return;
        this._container.destroy_all_children();

        const label = new St.Label({
            text: `AI Quota: ${message}`,
            style_class: 'antigravity-empty-label',
        });
        this._container.add_child(label);
    }

    _renderData(data) {
        if (!this._container) return;
        this._container.destroy_all_children();

        if (data.status !== 'ok') {
            const emptyLabel = new St.Label({
                text: data.message || 'Waiting for AI usage sync...',
                style_class: 'antigravity-empty-label',
            });
            this._container.add_child(emptyLabel);
            return;
        }

        // Header with Segmented Tab Switcher
        const headerBox = new St.BoxLayout({
            style_class: 'antigravity-header-box',
            x_expand: true,
        });

        // Tab Pill Box
        const tabBox = new St.BoxLayout({
            style_class: 'antigravity-tab-box',
            y_align: Clutter.ActorAlign.CENTER,
        });

        // Tab: Antigravity
        const isAgActive = this._activeTab === 'antigravity';
        const agTabBtn = new St.Button({
            label: 'Antigravity',
            style_class: `antigravity-tab-btn ${isAgActive ? 'antigravity-tab-btn-active' : ''}`,
            reactive: true,
            can_focus: true,
        });
        agTabBtn.connect('clicked', () => this._switchTab('antigravity'));
        tabBox.add_child(agTabBtn);

        // Tab: Codex
        const isCodexActive = this._activeTab === 'codex';
        const codexTabBtn = new St.Button({
            label: 'Codex',
            style_class: `antigravity-tab-btn ${isCodexActive ? 'antigravity-tab-btn-active' : ''}`,
            reactive: true,
            can_focus: true,
        });
        codexTabBtn.connect('clicked', () => this._switchTab('codex'));
        tabBox.add_child(codexTabBtn);

        headerBox.add_child(tabBox);

        // Spacer + Sync Label
        const spacer = new St.Widget({ x_expand: true });
        headerBox.add_child(spacer);

        const syncLabel = new St.Label({
            text: 'OMP',
            style_class: 'antigravity-sync-label',
            y_align: Clutter.ActorAlign.CENTER,
        });
        headerBox.add_child(syncLabel);

        this._container.add_child(headerBox);

        // Get accounts for current active tab
        let accounts = [];
        if (this._activeTab === 'codex') {
            accounts = data.providers?.codex?.accounts ?? [];
        } else {
            accounts = data.providers?.antigravity?.accounts ?? data.accounts ?? [];
        }

        if (accounts.length === 0) {
            const emptyMsg = this._activeTab === 'codex'
                ? 'No active OpenAI Codex accounts'
                : 'No active Google Antigravity accounts';
            const emptyLabel = new St.Label({
                text: emptyMsg,
                style_class: 'antigravity-empty-label',
            });
            this._container.add_child(emptyLabel);
            return;
        }

        // Render Account Cards
        for (const acc of accounts) {
            const card = new St.BoxLayout({
                vertical: true,
                style_class: 'antigravity-card',
                x_expand: true,
            });

            // Card Header: username + session badge
            const cardHeader = new St.BoxLayout({
                style_class: 'antigravity-card-header',
                x_expand: true,
            });
            const accountLabel = new St.Label({
                text: `● ${acc.display_name}`,
                style_class: 'antigravity-account-label',
                x_expand: true,
            });
            const badgeLabel = new St.Label({
                text: acc.is_active_session ? 'Active' : 'Session',
                style_class: 'antigravity-account-badge',
            });
            cardHeader.add_child(accountLabel);
            cardHeader.add_child(badgeLabel);
            card.add_child(cardHeader);

            // Metrics
            for (const m of acc.metrics) {
                const metricBox = new St.BoxLayout({
                    vertical: true,
                    style_class: 'antigravity-metric-row',
                    x_expand: true,
                });

                // Row Text: Label on left, Pct + Countdown on right
                const textBox = new St.BoxLayout({
                    style_class: 'antigravity-metric-text-box',
                    x_expand: true,
                });
                const labelText = new St.Label({
                    text: m.label,
                    style_class: 'antigravity-metric-label',
                    x_expand: true,
                });

                let colorClass = 'antigravity-color-safe';
                let fillClass = 'antigravity-progress-fill-safe';

                if (m.remaining_pct <= 0 || m.status === 'exhausted') {
                    colorClass = 'antigravity-color-exhausted';
                    fillClass = 'antigravity-progress-fill-exhausted';
                } else if (m.remaining_pct <= 20) {
                    colorClass = 'antigravity-color-warning';
                    fillClass = 'antigravity-progress-fill-warning';
                }

                const valueText = new St.Label({
                    text: `${m.remaining_pct}% · ${m.resets_in}`,
                    style_class: `antigravity-metric-pct ${colorClass}`,
                    y_align: Clutter.ActorAlign.CENTER,
                });
                textBox.add_child(labelText);
                textBox.add_child(valueText);
                metricBox.add_child(textBox);

                // Progress Bar Track
                const track = new St.BoxLayout({
                    style_class: 'antigravity-progress-track',
                    x_expand: true,
                });

                // Calculate fill width percentage
                const fillWidthPct = Math.max(0, Math.min(100, m.remaining_pct));
                if (fillWidthPct > 0) {
                    const fill = new St.Widget({
                        style_class: fillClass,
                        x_align: Clutter.ActorAlign.START,
                        x_expand: false,
                    });

                    // Initial conservative width
                    fill.set_width(Math.max(3, Math.round((fillWidthPct / 100.0) * 160)));

                    // Dynamically fit track's exact allocated width when rendered
                    track.connect('notify::allocation', () => {
                        const trackWidth = track.get_width();
                        if (trackWidth > 0) {
                            fill.set_width(Math.max(3, Math.round((fillWidthPct / 100.0) * trackWidth)));
                        }
                    });

                    track.add_child(fill);
                }

                metricBox.add_child(track);
                card.add_child(metricBox);
            }

            this._container.add_child(card);
        }
    }

    disable() {
        if (this._refreshTimeoutId) {
            GLib.source_remove(this._refreshTimeoutId);
            this._refreshTimeoutId = null;
        }

        if (this._dateMenu && this._openStateSignalId) {
            this._dateMenu.menu.disconnect(this._openStateSignalId);
            this._openStateSignalId = null;
        }

        if (this._container) {
            const parent = this._container.get_parent();
            if (parent) {
                parent.remove_child(this._container);
            }
            this._container.destroy();
            this._container = null;
        }

        this._dateMenu = null;
        this._cachedData = null;
    }
}
