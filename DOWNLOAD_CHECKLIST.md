# Complete Download Checklist for Vendor Libraries

## Download Status and Instructions

All files should be downloaded to: `c:\Users\arshi\OneDrive\Desktop\Work\Simurgh\Websites\CRM\core\static\vendor\`

---

## 1. ✅ Bootstrap 5.3.2
**Folder:** `bootstrap-5.3.2/`

Download from: https://github.com/twbs/bootstrap/releases/download/v5.3.2/bootstrap-5.3.2-dist.zip

Extract these files:
- `css/bootstrap.min.css` → `bootstrap-5.3.2/css/`
- `css/bootstrap.min.css.map` → `bootstrap-5.3.2/css/`
- `css/bootstrap.rtl.min.css` → `bootstrap-5.3.2/css/`
- `js/bootstrap.bundle.min.js` → `bootstrap-5.3.2/js/`
- `js/bootstrap.bundle.min.js.map` → `bootstrap-5.3.2/js/`

---

## 2. ✅ Font Awesome 6.4.2
**Folder:** `fontawesome-6.4.2/`

Download from: https://use.fontawesome.com/releases/v6.4.2/fontawesome-free-6.4.2-web.zip

Extract these files:
- `css/all.min.css` → `fontawesome-6.4.2/css/`
- `webfonts/*` → `fontawesome-6.4.2/webfonts/` (all font files)

---

## 3. ✅ jQuery 3.6.0
**Folder:** `jquery-3.6.0/`

Download: https://code.jquery.com/jquery-3.6.0.min.js
Save as: `jquery-3.6.0/jquery.min.js`

---

## 4. ✅ Select2 4.1.0-rc.0
**Folder:** `select2-4.1.0/`

Download from: https://github.com/select2/select2/releases/download/4.1.0-rc.0/select2-4.1.0-rc.0.zip

Extract these files:
- `dist/css/select2.min.css` → `select2-4.1.0/css/`
- `dist/js/select2.min.js` → `select2-4.1.0/js/`
- `dist/js/select2.full.min.js` → `select2-4.1.0/js/`

---

## 5. ✅ Chart.js 4.4.1
**Folder:** `chartjs-4.4.1/`

Download: https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js
Save as: `chartjs-4.4.1/chart.min.js`

---

## 6. ✅ SweetAlert2 11.10.5
**Folder:** `sweetalert2-11.10.5/`

Download:
- https://cdn.jsdelivr.net/npm/sweetalert2@11.10.5/dist/sweetalert2.all.min.js → `sweetalert2-11.10.5/sweetalert2.all.min.js`
- https://cdn.jsdelivr.net/npm/sweetalert2@11.10.5/dist/sweetalert2.min.css → `sweetalert2-11.10.5/sweetalert2.min.css`

---

## 7. ✅ Clipboard.js 2.0.8
**Folder:** `clipboard-2.0.8/`

Download: https://cdnjs.cloudflare.com/ajax/libs/clipboard.js/2.0.8/clipboard.min.js
Save as: `clipboard-2.0.8/clipboard.min.js`

---

## 8. ✅ Persian Datepicker 1.2.0
**Folder:** `persian-datepicker-1.2.0/`

Download:
- https://cdn.jsdelivr.net/npm/persian-date@1.1.0/dist/persian-date.min.js → `persian-datepicker-1.2.0/js/persian-date.min.js`
- https://cdn.jsdelivr.net/npm/persian-datepicker@1.2.0/dist/js/persian-datepicker.min.js → `persian-datepicker-1.2.0/js/persian-datepicker.min.js`
- https://cdn.jsdelivr.net/npm/persian-datepicker@1.2.0/dist/css/persian-datepicker.min.css → `persian-datepicker-1.2.0/css/persian-datepicker.min.css`

---

## 9. ✅ Vazir Font v30.1.0
**Folder:** `vazir-font-30.1.0/`

Download from: https://github.com/rastikerdar/vazir-font/releases/download/v30.1.0/vazir-font-v30.1.0.zip

Extract ALL font files to `vazir-font-30.1.0/` folder.
The `font-face.css` file has already been created.

---

## 10. ✅ Tailwind CSS 2.2.19
**Folder:** `tailwindcss-2.2.19/`

Download: https://cdn.jsdelivr.net/npm/tailwindcss@2.2.19/dist/tailwind.min.css
Save as: `tailwindcss-2.2.19/tailwind.min.css`

---

## 11. ✅ Leaflet 1.9.4
**Folder:** `leaflet-1.9.4/`

Download from: https://leafletjs.com/download.html or https://github.com/Leaflet/Leaflet/releases/download/v1.9.4/leaflet.zip

Extract:
- `leaflet.css` → `leaflet-1.9.4/css/`
- `leaflet.js` → `leaflet-1.9.4/js/`
- `images/*` → `leaflet-1.9.4/css/images/`

---

## 12. ✅ Tabulator 5.5.2
**Folder:** `tabulator-5.5.2/`

Download:
- https://unpkg.com/tabulator-tables@5.5.2/dist/css/tabulator_bootstrap5.min.css → `tabulator-5.5.2/css/`
- https://unpkg.com/tabulator-tables@5.5.2/dist/js/tabulator.min.js → `tabulator-5.5.2/js/`

---

## 13. ✅ XLSX (SheetJS) 0.17.0
**Folder:** `xlsx-0.17.0/`

Download: https://cdn.jsdelivr.net/npm/xlsx@0.17.0/dist/xlsx.full.min.js
Save as: `xlsx-0.17.0/xlsx.full.min.js`

---

## 14. ✅ Emoji Picker Element 1.21.0
**Folder:** `emoji-picker-element-1.21.0/`

Download: https://cdn.jsdelivr.net/npm/emoji-picker-element@1.21.0/index.js
Save as: `emoji-picker-element-1.21.0/index.js`

Note: This is an ES module and may require additional files from the package.

---

## Summary

**Total Libraries:** 14
**Estimated Total Size:** ~15-20 MB

## After Downloading

1. Run: `python manage.py collectstatic`
2. Test the website thoroughly
3. Check browser console for any 404 errors
4. Verify all features work (charts, datepickers, icons, etc.)
