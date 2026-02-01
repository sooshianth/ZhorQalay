# Vendor Libraries Download Guide

This guide provides download links and instructions for all external dependencies needed to make the website independent.

## Download Instructions

All files should be downloaded and placed in the specified directories under:
`c:\Users\arshi\OneDrive\Desktop\Work\Simurgh\Websites\CRM\core\static\vendor\`

---

## 1. Bootstrap 5.3.2
**Directory:** `core/static/vendor/bootstrap-5.3.2/`

**Download Link:** https://github.com/twbs/bootstrap/releases/download/v5.3.2/bootstrap-5.3.2-dist.zip

**Files to extract:**
- `css/bootstrap.min.css` → `bootstrap-5.3.2/css/bootstrap.min.css`
- `css/bootstrap.min.css.map` → `bootstrap-5.3.2/css/bootstrap.min.css.map`
- `css/bootstrap.rtl.min.css` → `bootstrap-5.3.2/css/bootstrap.rtl.min.css`
- `css/bootstrap.rtl.min.css.map` → `bootstrap-5.3.2/css/bootstrap.rtl.min.css.map`
- `js/bootstrap.bundle.min.js` → `bootstrap-5.3.2/js/bootstrap.bundle.min.js`
- `js/bootstrap.bundle.min.js.map` → `bootstrap-5.3.2/js/bootstrap.bundle.min.js.map`

---

## 2. Font Awesome 6.4.2
**Directory:** `core/static/vendor/fontawesome-6.4.2/`

**Download Link:** https://use.fontawesome.com/releases/v6.4.2/fontawesome-free-6.4.2-web.zip

**Files to extract:**
- `css/all.min.css` → `fontawesome-6.4.2/css/all.min.css`
- `webfonts/*` → `fontawesome-6.4.2/webfonts/` (all font files)

---

## 3. jQuery 3.6.0
**Directory:** `core/static/vendor/jquery-3.6.0/`

**Download Links:**
- https://code.jquery.com/jquery-3.6.0.min.js → `jquery-3.6.0/jquery.min.js`

---

## 4. Select2 4.1.0-rc.0
**Directory:** `core/static/vendor/select2-4.1.0/`

**Download Link:** https://github.com/select2/select2/archive/refs/tags/4.1.0-rc.0.zip

**Files to extract:**
- `dist/css/select2.min.css` → `select2-4.1.0/css/select2.min.css`
- `dist/js/select2.min.js` → `select2-4.1.0/js/select2.min.js`
- `dist/js/select2.full.min.js` → `select2-4.1.0/js/select2.full.min.js`

---

## 5. Chart.js 4.4.1
**Directory:** `core/static/vendor/chartjs-4.4.1/`

**Download Links:**
- https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js → `chartjs-4.4.1/chart.min.js`

Or use direct CDN download:
- https://github.com/chartjs/Chart.js/releases/download/v4.4.1/chart.js-4.4.1.tgz

---

## 6. SweetAlert2 11.10.5
**Directory:** `core/static/vendor/sweetalert2-11.10.5/`

**Download Links:**
- https://cdn.jsdelivr.net/npm/sweetalert2@11.10.5/dist/sweetalert2.all.min.js → `sweetalert2-11.10.5/sweetalert2.all.min.js`
- https://cdn.jsdelivr.net/npm/sweetalert2@11.10.5/dist/sweetalert2.min.css → `sweetalert2-11.10.5/sweetalert2.min.css`

---

## 7. Clipboard.js 2.0.8
**Directory:** `core/static/vendor/clipboard-2.0.8/`

**Download Links:**
- https://cdnjs.cloudflare.com/ajax/libs/clipboard.js/2.0.8/clipboard.min.js → `clipboard-2.0.8/clipboard.min.js`

---

## 8. Persian Datepicker 1.2.0
**Directory:** `core/static/vendor/persian-datepicker-1.2.0/`

**Download Links:**
- https://cdn.jsdelivr.net/npm/persian-date@1.1.0/dist/persian-date.min.js → `persian-datepicker-1.2.0/js/persian-date.min.js`
- https://cdn.jsdelivr.net/npm/persian-datepicker@1.2.0/dist/js/persian-datepicker.min.js → `persian-datepicker-1.2.0/js/persian-datepicker.min.js`
- https://cdn.jsdelivr.net/npm/persian-datepicker@1.2.0/dist/css/persian-datepicker.min.css → `persian-datepicker-1.2.0/css/persian-datepicker.min.css`

**Alternative (unpkg):**
- https://unpkg.com/persian-date@latest/dist/persian-date.min.js
- https://unpkg.com/persian-datepicker@latest/dist/js/persian-datepicker.min.js
- https://unpkg.com/persian-datepicker@latest/dist/css/persian-datepicker.min.css

---

## 9. Vazir Font v30.1.0
**Directory:** `core/static/vendor/vazir-font-30.1.0/`

**Download Link:** https://github.com/rastikerdar/vazir-font/releases/download/v30.1.0/vazir-font-v30.1.0.zip

**Files to extract:**
- `Vazir.woff2` → `vazir-font-30.1.0/Vazir.woff2`
- `Vazir.woff` → `vazir-font-30.1.0/Vazir.woff`
- `Vazir.ttf` → `vazir-font-30.1.0/Vazir.ttf`
- `Vazir-Bold.woff2` → `vazir-font-30.1.0/Vazir-Bold.woff2`
- `Vazir-Bold.woff` → `vazir-font-30.1.0/Vazir-Bold.woff`
- `Vazir-Bold.ttf` → `vazir-font-30.1.0/Vazir-Bold.ttf`
- `Vazir-Regular.ttf` → `vazir-font-30.1.0/Vazir-Regular.ttf`

**Also create a font-face.css file** in `vazir-font-30.1.0/font-face.css` with this content:
```css
@font-face {
    font-family: Vazir;
    src: url('Vazir.woff2') format('woff2'),
         url('Vazir.woff') format('woff'),
         url('Vazir.ttf') format('truetype');
    font-weight: normal;
    font-style: normal;
}

@font-face {
    font-family: Vazir;
    src: url('Vazir-Bold.woff2') format('woff2'),
         url('Vazir-Bold.woff') format('woff'),
         url('Vazir-Bold.ttf') format('truetype');
    font-weight: bold;
    font-style: normal;
}
```

---

## 10. Tailwind CSS 2.2.19
**Directory:** `core/static/vendor/tailwindcss-2.2.19/`

**Download Links:**
- https://cdn.jsdelivr.net/npm/tailwindcss@2.2.19/dist/tailwind.min.css → `tailwindcss-2.2.19/tailwind.min.css`

**Note:** For production, consider building Tailwind properly with your configuration.

---

## 11. Leaflet 1.9.4 (Maps)
**Directory:** `core/static/vendor/leaflet-1.9.4/`

**Download Link:** https://cdn.leafletjs.com/leaflet-1.9.4.zip

**Files to extract:**
- `leaflet.css` → `leaflet-1.9.4/css/leaflet.css`
- `leaflet.js` → `leaflet-1.9.4/js/leaflet.js`
- `images/*` → `leaflet-1.9.4/css/images/` (all image files)

---

## 12. Tabulator 5.5.2 (Advanced Tables)
**Directory:** `core/static/vendor/tabulator-5.5.2/`

**Download Links:**
- https://unpkg.com/tabulator-tables@5.5.2/dist/css/tabulator_bootstrap5.min.css → `tabulator-5.5.2/css/tabulator_bootstrap5.min.css`
- https://unpkg.com/tabulator-tables@5.5.2/dist/js/tabulator.min.js → `tabulator-5.5.2/js/tabulator.min.js`

---

## 13. XLSX (SheetJS) 0.17.0
**Directory:** `core/static/vendor/xlsx-0.17.0/`

**Download Links:**
- https://cdn.jsdelivr.net/npm/xlsx@0.17.0/dist/xlsx.full.min.js → `xlsx-0.17.0/xlsx.full.min.js`

---

## 14. Emoji Picker Element 1.21.0
**Directory:** `core/static/vendor/emoji-picker-element-1.21.0/`

**Download Links:**
- https://cdn.jsdelivr.net/npm/emoji-picker-element@1.21.0/index.js → `emoji-picker-element-1.21.0/index.js`
- https://cdn.jsdelivr.net/npm/emoji-picker-element@1.21.0/picker.js → `emoji-picker-element-1.21.0/picker.js`

**Note:** This is an ES module. You may need additional files from the package.

---

## Quick Download Script (PowerShell)

You can use this PowerShell script to download all files automatically:

```powershell
# Set the base directory
$baseDir = "c:\Users\arshi\OneDrive\Desktop\Work\Simurgh\Websites\CRM\core\static\vendor"

# Download function
function Download-File {
    param($url, $output)
    Write-Host "Downloading: $output"
    Invoke-WebRequest -Uri $url -OutFile $output
}

# Bootstrap
Download-File "https://github.com/twbs/bootstrap/releases/download/v5.3.2/bootstrap-5.3.2-dist.zip" "$baseDir\bootstrap-5.3.2.zip"
Expand-Archive "$baseDir\bootstrap-5.3.2.zip" "$baseDir\bootstrap-5.3.2-temp"
Move-Item "$baseDir\bootstrap-5.3.2-temp\bootstrap-5.3.2-dist\css\*" "$baseDir\bootstrap-5.3.2\css\"
Move-Item "$baseDir\bootstrap-5.3.2-temp\bootstrap-5.3.2-dist\js\*" "$baseDir\bootstrap-5.3.2\js\"
Remove-Item "$baseDir\bootstrap-5.3.2.zip"
Remove-Item "$baseDir\bootstrap-5.3.2-temp" -Recurse

# Font Awesome
Download-File "https://use.fontawesome.com/releases/v6.4.2/fontawesome-free-6.4.2-web.zip" "$baseDir\fontawesome-6.4.2.zip"
Expand-Archive "$baseDir\fontawesome-6.4.2.zip" "$baseDir\fontawesome-6.4.2-temp"
Move-Item "$baseDir\fontawesome-6.4.2-temp\fontawesome-free-6.4.2-web\css\*" "$baseDir\fontawesome-6.4.2\css\"
Move-Item "$baseDir\fontawesome-6.4.2-temp\fontawesome-free-6.4.2-web\webfonts\*" "$baseDir\fontawesome-6.4.2\webfonts\"
Remove-Item "$baseDir\fontawesome-6.4.2.zip"
Remove-Item "$baseDir\fontawesome-6.4.2-temp" -Recurse

# jQuery
Download-File "https://code.jquery.com/jquery-3.6.0.min.js" "$baseDir\jquery-3.6.0\jquery.min.js"

# Chart.js
Download-File "https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js" "$baseDir\chartjs-4.4.1\chart.min.js"

# SweetAlert2
Download-File "https://cdn.jsdelivr.net/npm/sweetalert2@11.10.5/dist/sweetalert2.all.min.js" "$baseDir\sweetalert2-11.10.5\sweetalert2.all.min.js"
Download-File "https://cdn.jsdelivr.net/npm/sweetalert2@11.10.5/dist/sweetalert2.min.css" "$baseDir\sweetalert2-11.10.5\sweetalert2.min.css"

# Clipboard.js
Download-File "https://cdnjs.cloudflare.com/ajax/libs/clipboard.js/2.0.8/clipboard.min.js" "$baseDir\clipboard-2.0.8\clipboard.min.js"

# Persian Datepicker
Download-File "https://cdn.jsdelivr.net/npm/persian-date@1.1.0/dist/persian-date.min.js" "$baseDir\persian-datepicker-1.2.0\js\persian-date.min.js"
Download-File "https://cdn.jsdelivr.net/npm/persian-datepicker@1.2.0/dist/js/persian-datepicker.min.js" "$baseDir\persian-datepicker-1.2.0\js\persian-datepicker.min.js"
Download-File "https://cdn.jsdelivr.net/npm/persian-datepicker@1.2.0/dist/css/persian-datepicker.min.css" "$baseDir\persian-datepicker-1.2.0\css\persian-datepicker.min.css"

# Vazir Font
Download-File "https://github.com/rastikerdar/vazir-font/releases/download/v30.1.0/vazir-font-v30.1.0.zip" "$baseDir\vazir-font-30.1.0.zip"
Expand-Archive "$baseDir\vazir-font-30.1.0.zip" "$baseDir\vazir-font-30.1.0"
Remove-Item "$baseDir\vazir-font-30.1.0.zip"

# Tailwind CSS
Download-File "https://cdn.jsdelivr.net/npm/tailwindcss@2.2.19/dist/tailwind.min.css" "$baseDir\tailwindcss-2.2.19\tailwind.min.css"

# Leaflet
Download-File "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" "$baseDir\leaflet-1.9.4\css\leaflet.css"
Download-File "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js" "$baseDir\leaflet-1.9.4\js\leaflet.js"

# Tabulator
Download-File "https://unpkg.com/tabulator-tables@5.5.2/dist/css/tabulator_bootstrap5.min.css" "$baseDir\tabulator-5.5.2\css\tabulator_bootstrap5.min.css"
Download-File "https://unpkg.com/tabulator-tables@5.5.2/dist/js/tabulator.min.js" "$baseDir\tabulator-5.5.2\js\tabulator.min.js"

# XLSX
Download-File "https://cdn.jsdelivr.net/npm/xlsx@0.17.0/dist/xlsx.full.min.js" "$baseDir\xlsx-0.17.0\xlsx.full.min.js"

# Select2
Download-File "https://cdn.jsdelivr.net/npm/select2@4.1.0-rc.0/dist/css/select2.min.css" "$baseDir\select2-4.1.0\css\select2.min.css"
Download-File "https://cdn.jsdelivr.net/npm/select2@4.1.0-rc.0/dist/js/select2.min.js" "$baseDir\select2-4.1.0\js\select2.min.js"
Download-File "https://cdn.jsdelivr.net/npm/select2@4.1.0-rc.0/dist/js/select2.full.min.js" "$baseDir\select2-4.1.0\js\select2.full.min.js"

Write-Host "All downloads completed!"
```

---

## After Downloading

After downloading all files:

1. Run `python manage.py collectstatic` to collect all static files to the STATIC_ROOT
2. Test the website to ensure all resources load correctly
3. Check browser console for any 404 errors
4. Verify fonts, icons, and JavaScript functionality work properly

---

## Notes

- The `static` folder that gets generated by `collectstatic` is gitignored - that's correct, don't touch it
- All vendor files are placed in `core/static/vendor/` which will be included in collectstatic
- Font file paths in CSS may need adjustment after download
- Some libraries may have dependencies on other libraries (e.g., Select2 needs jQuery)
