(function () {
  function resetSelect(selectEl, placeholderText, disabled) {
    selectEl.innerHTML = "";
    var opt = document.createElement("option");
    opt.value = "";
    opt.textContent = placeholderText;
    selectEl.appendChild(opt);
    if (typeof disabled === "boolean") {
      selectEl.disabled = disabled;
    }
  }

  function appendOption(selectEl, value, label) {
    var opt = document.createElement("option");
    opt.value = value;
    opt.textContent = label;
    selectEl.appendChild(opt);
  }

  function getSelectedText(selectEl) {
    if (!selectEl || selectEl.selectedIndex < 0) {
      return "";
    }
    var option = selectEl.options[selectEl.selectedIndex];
    return option ? (option.textContent || "").trim() : "";
  }

  async function fetchJson(url) {
    var response = await fetch(url, { headers: { Accept: "application/json" } });
    if (!response.ok) {
      throw new Error("Request failed");
    }
    return response.json();
  }

  async function loadCities(provinceSelect, citySelect, selectedCityId) {
    var provinceId = (provinceSelect.value || "").trim();
    if (!provinceId) {
      resetSelect(citySelect, "ابتدا استان را انتخاب کنید...", true);
      return;
    }

    resetSelect(citySelect, "در حال بارگذاری شهرها...", true);
    try {
      var url =
        "/api/geography/cities/?province_id=" +
        encodeURIComponent(provinceId) +
        "&with_ids=1";
      var data = await fetchJson(url);

      resetSelect(citySelect, "انتخاب کنید...", false);
      if (Array.isArray(data)) {
        data.forEach(function (item) {
          if (!item || typeof item !== "object") return;
          appendOption(citySelect, item.id, item.name);
        });
      }

      if (selectedCityId) {
        citySelect.value = selectedCityId;
      }
    } catch (e) {
      resetSelect(citySelect, "خطا در دریافت شهرها", true);
    }
  }

  function fillPlaceSelect(selectEl, items, placeholderText) {
    resetSelect(selectEl, placeholderText, false);
    if (!Array.isArray(items)) {
      return;
    }
    items.forEach(function (item) {
      if (!item || typeof item !== "object") return;
      appendOption(selectEl, item.id, item.name);
    });
  }

  async function loadPlaces(provinceSelect, citySelect, schoolSelect, mosqueSelect, selectedSchoolId, selectedMosqueId) {
    var provinceId = (provinceSelect.value || "").trim();
    var cityId = (citySelect.value || "").trim();

    if (!schoolSelect && !mosqueSelect) {
      return;
    }

    if (!provinceId || !cityId) {
      if (schoolSelect) {
        resetSelect(schoolSelect, "ابتدا شهر را انتخاب کنید...", false);
      }
      if (mosqueSelect) {
        resetSelect(mosqueSelect, "ابتدا شهر را انتخاب کنید...", false);
      }
      return;
    }

    if (schoolSelect) {
      fillPlaceSelect(schoolSelect, [], "در حال بارگذاری مدارس...");
    }
    if (mosqueSelect) {
      fillPlaceSelect(mosqueSelect, [], "در حال بارگذاری مساجد...");
    }

    var provinceName = getSelectedText(provinceSelect);
    var cityName = getSelectedText(citySelect);
    var query =
      "province_id=" +
      encodeURIComponent(provinceId) +
      "&city_id=" +
      encodeURIComponent(cityId) +
      "&province=" +
      encodeURIComponent(provinceName) +
      "&city=" +
      encodeURIComponent(cityName);

    try {
      var results = await Promise.all([
        schoolSelect ? fetchJson("/api/geography/schools/?" + query) : Promise.resolve([]),
        mosqueSelect ? fetchJson("/api/geography/mosques/?" + query) : Promise.resolve([]),
      ]);
      var schoolData = results[0] && (results[0].results || results[0]);
      var mosqueData = results[1] && (results[1].results || results[1]);

      if (schoolSelect) {
        fillPlaceSelect(schoolSelect, schoolData, "انتخاب مدرسه...");
        if (selectedSchoolId) {
          schoolSelect.value = selectedSchoolId;
        }
      }
      if (mosqueSelect) {
        fillPlaceSelect(mosqueSelect, mosqueData, "انتخاب مسجد...");
        if (selectedMosqueId) {
          mosqueSelect.value = selectedMosqueId;
        }
      }
    } catch (e) {
      if (schoolSelect) {
        resetSelect(schoolSelect, "خطا در دریافت مدارس", false);
      }
      if (mosqueSelect) {
        resetSelect(mosqueSelect, "خطا در دریافت مساجد", false);
      }
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    var provinceSelect = document.getElementById("id_province_ref");
    var citySelect = document.getElementById("id_city_ref");
    var schoolSelect = document.getElementById("id_school");
    var mosqueSelect = document.getElementById("id_mosque");
    if (!provinceSelect || !citySelect) return;

    var initialCity = (citySelect.value || "").trim();
    var initialSchool = schoolSelect ? (schoolSelect.value || "").trim() : "";
    var initialMosque = mosqueSelect ? (mosqueSelect.value || "").trim() : "";

    loadCities(provinceSelect, citySelect, initialCity).then(function () {
      return loadPlaces(
        provinceSelect,
        citySelect,
        schoolSelect,
        mosqueSelect,
        initialSchool,
        initialMosque
      );
    });

    provinceSelect.addEventListener("change", function () {
      if (schoolSelect) {
        resetSelect(schoolSelect, "ابتدا شهر را انتخاب کنید...", false);
      }
      if (mosqueSelect) {
        resetSelect(mosqueSelect, "ابتدا شهر را انتخاب کنید...", false);
      }
      loadCities(provinceSelect, citySelect, "").then(function () {
        loadPlaces(provinceSelect, citySelect, schoolSelect, mosqueSelect, "", "");
      });
    });

    citySelect.addEventListener("change", function () {
      loadPlaces(provinceSelect, citySelect, schoolSelect, mosqueSelect, "", "");
    });
  });
})();
