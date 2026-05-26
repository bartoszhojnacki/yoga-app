const PRESETS = [
  { id: "morning", tab: "yoga", icon: "🌅", label: "Poranek",
    apply: (f) => Object.assign(f.yoga, { style: ["Poranna"], minDur: 0, maxDur: 30, minInt: 2, maxInt: 3 }) },
  { id: "evening", tab: "yoga", icon: "🌙", label: "Wyciszenie",
    apply: (f) => Object.assign(f.yoga, { style: ["Spokojna / Yin"], minDur: 15, maxDur: 90, minInt: 1, maxInt: 2 }) },
  { id: "power", tab: "yoga", icon: "💪", label: "Energia",
    apply: (f) => Object.assign(f.yoga, { style: ["Dynamiczna / Vinyasa"], minDur: 20, maxDur: 90, minInt: 4, maxInt: 5 }) },
  { id: "hips", tab: "mobility", icon: "🔓", label: "Biodra",
    apply: (f) => Object.assign(f.mobility, { body: ["Biodra"], minDur: 0, maxDur: 60 }) },
  { id: "back", tab: "mobility", icon: "🧱", label: "Plecy",
    apply: (f) => Object.assign(f.mobility, { body: ["Kręgosłup"], minDur: 0, maxDur: 30 }) },
  { id: "quick", tab: null, icon: "⚡", label: "Krótkie",
    apply: (f) => { f.yoga.maxDur = 15; f.mobility.maxDur = 15; } },
];

const TAXONOMY = {
  yogaStyle: ["Spokojna / Yin", "Dynamiczna / Vinyasa", "Poranna", "Dla początkujących"],
  yogaFocus: ["Kręgosłup", "Biodra", "Brzuch / Core", "Całe ciało"],
  mobilityType: ["Stretching", "Mobility", "Rolowanie", "Wzmacnianie"],
  mobilityBody: ["Biodra", "Barki & Szyja", "Kręgosłup", "Nogi", "Nadgarstki", "Całe ciało"],
};

const FAV_KEY = "studio.favorites.v1";
const USAGE_KEY = "studio.usage.v1";

function defaultFilters() {
  return {
    yoga: { style: [], focus: [], channel: [], minDur: 0, maxDur: 120, minInt: 1, maxInt: 5, search: "" },
    mobility: { type: [], body: [], channel: [], minDur: 0, maxDur: 90, search: "" },
  };
}

document.addEventListener("alpine:init", () => {
  Alpine.data("studio", () => ({
    loaded: false,
    activeTab: localStorage.getItem("studio.tab") || "yoga",
    data: { yoga: [], mobility: [] },
    counts: { yoga: 0, mobility: 0 },
    totalCount: 0,
    lastUpdate: "",
    channels: { yoga: [], mobility: [] },
    taxonomy: TAXONOMY,
    presets: PRESETS,
    activePreset: null,
    onlyFavorites: false,
    visibleLimit: 30,
    sort: "duration_asc",
    favorites: new Set(),
    usage: {},
    filters: defaultFilters(),

    async init() {
      this.favorites = new Set(JSON.parse(localStorage.getItem(FAV_KEY) || "[]"));
      this.usage = JSON.parse(localStorage.getItem(USAGE_KEY) || "{}");

      try {
        const [yogaRes, mobRes] = await Promise.all([
          fetch("data/yoga.json"),
          fetch("data/mobility.json"),
        ]);
        const yoga = await yogaRes.json();
        const mob = await mobRes.json();
        this.data.yoga = yoga.videos || [];
        this.data.mobility = mob.videos || [];
        this.counts.yoga = this.data.yoga.length;
        this.counts.mobility = this.data.mobility.length;
        this.totalCount = this.counts.yoga + this.counts.mobility;
        this.channels.yoga = [...new Set(this.data.yoga.map(v => v.channel))].sort();
        this.channels.mobility = [...new Set(this.data.mobility.map(v => v.channel))].sort();
        const upd = yoga.updated_at || mob.updated_at;
        this.lastUpdate = upd ? new Date(upd).toLocaleDateString("pl-PL") : "";
        this.loaded = true;
      } catch (e) {
        console.error("Nie udało się załadować danych", e);
        document.querySelector(".loader").textContent = "Błąd ładowania danych. Sprawdź konsolę.";
      }
    },

    setTab(tab) {
      this.activeTab = tab;
      this.activePreset = null;
      this.visibleLimit = 30;
      localStorage.setItem("studio.tab", tab);
    },

    availablePresets() {
      return PRESETS.filter(p => !p.tab || p.tab === this.activeTab);
    },

    togglePreset(id) {
      const p = PRESETS.find(x => x.id === id);
      if (!p) return;
      if (this.activePreset === id) {
        this.resetFilters();
        return;
      }
      if (p.tab && p.tab !== this.activeTab) this.setTab(p.tab);
      this.filters = defaultFilters();
      p.apply(this.filters);
      this.activePreset = id;
      this.visibleLimit = 30;
    },

    resetFilters() {
      this.filters = defaultFilters();
      this.activePreset = null;
      this.onlyFavorites = false;
      this.visibleLimit = 30;
    },

    toggleOnlyFavs() {
      this.onlyFavorites = !this.onlyFavorites;
      this.visibleLimit = 30;
    },

    filteredVideos() {
      const tab = this.activeTab;
      const f = this.filters[tab];
      const minDur = Math.min(f.minDur, f.maxDur);
      const maxDur = Math.max(f.minDur, f.maxDur);
      const search = (f.search || "").toLowerCase().trim();

      let list = this.data[tab].filter(v => {
        if (v.duration < minDur || v.duration > maxDur) return false;
        if (f.channel.length && !f.channel.includes(v.channel)) return false;
        if (this.onlyFavorites && !this.favorites.has(v.id)) return false;

        if (tab === "yoga") {
          const intMin = Math.min(f.minInt, f.maxInt);
          const intMax = Math.max(f.minInt, f.maxInt);
          if (v.intensity < intMin || v.intensity > intMax) return false;
          if (f.style.length && !f.style.some(s => v.style.includes(s))) return false;
          if (f.focus.length && !f.focus.some(s => v.focus.includes(s))) return false;
        } else {
          if (f.type.length && !f.type.some(s => v.type_tags.includes(s))) return false;
          if (f.body.length && !f.body.some(s => v.body_tags.includes(s))) return false;
        }
        if (search) {
          const blob = `${v.title} ${v.description || ""}`.toLowerCase();
          if (!blob.includes(search)) return false;
        }
        return true;
      });

      const usage = this.usage;
      const sorters = {
        duration_asc: (a, b) => a.duration - b.duration,
        duration_desc: (a, b) => b.duration - a.duration,
        title_asc: (a, b) => a.title.localeCompare(b.title, "pl"),
        usage_desc: (a, b) => (usage[b.id] || 0) - (usage[a.id] || 0),
      };
      list.sort(sorters[this.sort] || sorters.duration_asc);
      return list;
    },

    randomFromCurrent() {
      const list = this.filteredVideos();
      if (!list.length) return;
      const pick = list[Math.floor(Math.random() * list.length)];
      this.incrementUsage(pick.id);
      window.open(pick.url, "_blank", "noopener");
    },

    isFavorite(id) { return this.favorites.has(id); },

    toggleFavorite(id) {
      if (this.favorites.has(id)) this.favorites.delete(id);
      else this.favorites.add(id);
      localStorage.setItem(FAV_KEY, JSON.stringify([...this.favorites]));
    },

    usageCount(id) { return this.usage[id] || 0; },

    incrementUsage(id) {
      this.usage[id] = (this.usage[id] || 0) + 1;
      localStorage.setItem(USAGE_KEY, JSON.stringify(this.usage));
    },

    intensityDots(level) {
      const lvl = Math.max(1, Math.min(5, parseInt(level) || 1));
      return "●".repeat(lvl) + "○".repeat(5 - lvl);
    },

    truncate(text, n) {
      if (!text) return "";
      return text.length > n ? text.slice(0, n).trim() + "…" : text;
    },
  }));
});
