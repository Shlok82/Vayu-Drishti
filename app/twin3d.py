"""3D Digital Twin payload construction and telemetry packaging.

Builds JSON-serializable payloads combining replay telemetry, debounced state,
and module wear distributions for the 3D twin visualization.
"""

from typing import Any, Dict, List, Sequence, Union
import json
import numpy as np
import pandas as pd
from ml.module_wear import module_wear_series, wear_from_rul

TWIN_DISCLAIMER = (
    "Illustrative module wear: engine-level predicted RUL allocated to modules "
    "with fixed factors. C-MAPSS has no per-module labels. Synthetic demo, not real fleet data."
)


def build_twin_payload(
    aircraft_id: str,
    engine_id: Union[int, str],
    replay_df: pd.DataFrame,
    debounced_status: Sequence[str],
    debounced_risk: Sequence[str],
    dates: Sequence[Any],
    engine2_rul: Union[float, int],
    engine2_risk: str,
) -> Dict[str, Any]:
    """Construct JSON-serializable payload for the 3D digital twin visualization.

    Does NOT import any Streamlit app pages. Caller supplies debounced status,
    risk, and cycle dates calculated from fleet/aircraft metadata.

    Args:
        aircraft_id: Aircraft identifier (e.g. 'AF-1001').
        engine_id: Primary engine identifier (e.g. 71).
        replay_df: DataFrame containing engine_1 replay cycles and predicted_rul.
        debounced_status: Sequence of debounced spares status strings per cycle.
        debounced_risk: Sequence of debounced risk level strings per cycle.
        dates: Sequence of cycle timestamp/date strings from the twin page logic.
        engine2_rul: Static predicted RUL cycles for engine_2.
        engine2_risk: Static risk level string for engine_2.

    Returns:
        JSON-serializable dict conforming to the twin payload schema.
    """
    cycles_list = [int(c) for c in replay_df["cycle"]]
    rul_list = [round(float(r), 1) for r in replay_df["predicted_rul"]]
    dates_list = [str(d) for d in dates]
    status_list = [str(s) for s in debounced_status]
    risk_list = [str(r) for r in debounced_risk]

    e1_wear = module_wear_series(rul_list)
    e2_wear = wear_from_rul(float(engine2_rul))

    payload: Dict[str, Any] = {
        "version": 1,
        "disclaimer": TWIN_DISCLAIMER,
        "aircraft_id": str(aircraft_id),
        "engine1": {
            "engine_id": int(engine_id),
            "cycles": cycles_list,
            "dates": dates_list,
            "rul": rul_list,
            "risk": risk_list,
            "status": status_list,
            "wear": {
                "fan": e1_wear["fan"],
                "compressor": e1_wear["compressor"],
                "combustor": e1_wear["combustor"],
                "turbine": e1_wear["turbine"],
            },
        },
        "engine2": {
            "static": True,
            "rul": round(float(engine2_rul), 1),
            "risk": str(engine2_risk),
            "wear": {
                "fan": round(float(e2_wear["fan"]), 1),
                "compressor": round(float(e2_wear["compressor"]), 1),
                "combustor": round(float(e2_wear["combustor"]), 1),
                "turbine": round(float(e2_wear["turbine"]), 1),
            },
            "note": "Static: engine 2 has no replay; value comes from predictions.csv.",
        },
    }

    return payload


TWIN3D_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Vayu Drishti - 3D Digital Twin</title>
<script src="https://cdn.jsdelivr.net/npm/three@0.128.0/build/three.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js"></script>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { margin: 0; padding: 0; background: #eef2f6; overflow: hidden; font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
#twin3d-root { width: 100%; min-height: 480px; height: 560px; position: relative; overflow: hidden; background: #eef2f6; user-select: none; }
#canvas-container { position: absolute; top: 0; left: 0; width: 100%; height: 100%; z-index: 1; }
#top-bar { position: absolute; top: 12px; left: 12px; z-index: 10; display: flex; gap: 6px; align-items: center; flex-wrap: wrap; }
.btn-twin { background: rgba(255, 255, 255, 0.90); border: 1px solid #cbd5e1; color: #1e293b; font-size: 11px; font-weight: 600; padding: 5px 10px; border-radius: 6px; cursor: pointer; box-shadow: 0 1px 2px rgba(0,0,0,0.05); transition: all 0.15s ease; outline: none; }
.btn-twin:hover { background: #ffffff; border-color: #94a3b8; }
.btn-twin.active { background: #0284c7; color: #ffffff; border-color: #0284c7; }
#ac-badge { position: absolute; top: 12px; right: 12px; z-index: 10; background: rgba(15, 23, 42, 0.85); color: #f8fafc; font-size: 12px; font-weight: 700; padding: 5px 10px; border-radius: 6px; letter-spacing: 0.5px; }
#bottom-bar { position: absolute; bottom: 26px; left: 12px; right: 12px; z-index: 10; background: rgba(255, 255, 255, 0.92); backdrop-filter: blur(8px); border: 1px solid #cbd5e1; border-radius: 8px; padding: 8px 12px; display: flex; flex-direction: column; gap: 6px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); }
.bottom-row { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; width: 100%; }
.speed-group { display: flex; gap: 2px; }
.btn-spd { padding: 4px 7px; font-size: 10px; border-radius: 4px; }
.status-pill { padding: 3px 8px; border-radius: 4px; font-size: 11px; font-weight: 700; text-transform: uppercase; color: #ffffff; }
#twin-caption { position: absolute; bottom: 4px; left: 12px; right: 12px; z-index: 10; font-size: 10px; color: #64748b; text-align: center; pointer-events: none; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.twin-label { position: absolute; pointer-events: none; background: rgba(15, 23, 42, 0.85); color: #f8fafc; font-size: 11px; font-weight: 600; padding: 3px 8px; border-radius: 4px; border: 1px solid rgba(255, 255, 255, 0.25); transform: translate(-50%, -100%); white-space: nowrap; z-index: 5; transition: opacity 0.15s; }
#labels-layer { position: absolute; top: 0; left: 0; width: 100%; height: 100%; pointer-events: none; z-index: 5; }
#error-fallback { display: none; position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); z-index: 50; background: #fee2e2; border: 1px solid #ef4444; color: #991b1b; padding: 16px 20px; border-radius: 8px; font-size: 13px; text-align: center; max-width: 85%; }
</style>
</head>
<body>
<div id="twin3d-root">
<div id="error-fallback">
<strong>3D view unavailable (WebGL or network). The 2D twin below still works.</strong>
<div id="error-details" style="font-size: 11px; margin-top: 6px; color: #7f1d1d;"></div>
</div>
<div id="canvas-container"></div>
<div id="top-bar">
<button type="button" class="btn-twin active" id="btn-condition">Condition</button>
<button type="button" class="btn-twin" id="btn-xray">X-ray</button>
<button type="button" class="btn-twin active" id="btn-alerts">Alerts</button>
<button type="button" class="btn-twin" id="btn-reset">Reset View</button>
</div>
<div id="ac-badge">AIRCRAFT</div>
<div id="labels-layer">
<div class="twin-label" id="lbl-fan">Fan wear 0.0%</div>
<div class="twin-label" id="lbl-comp">Compressor wear 0.0%</div>
<div class="twin-label" id="lbl-comb">Combustor wear 0.0%</div>
<div class="twin-label" id="lbl-turb">Turbine wear 0.0%</div>
<div class="twin-label" id="lbl-eng2">Engine 2 (static)</div>
</div>
<div id="bottom-bar">
<div class="bottom-row">
<button type="button" class="btn-twin" id="btn-play" style="min-width: 60px;">Play</button>
<input type="range" id="cycle-slider" min="0" max="0" value="0" style="flex: 1; cursor: pointer;">
<div class="speed-group">
<button type="button" class="btn-twin btn-spd active" id="btn-spd-1">1x</button>
<button type="button" class="btn-twin btn-spd" id="btn-spd-3">3x</button>
<button type="button" class="btn-twin btn-spd" id="btn-spd-8">8x</button>
</div>
</div>
<div class="bottom-row" style="justify-content: space-between;">
<div style="display: flex; gap: 12px; align-items: center;">
<span id="disp-cycle" style="font-weight: 600; font-size: 11px; color: #1e293b;">Cycle 1 / 1</span>
<span id="disp-date" style="font-size: 11px; color: #64748b;">2026-10-20 09:00</span>
</div>
<span id="disp-status" class="status-pill" style="background: #16a34a; color: #ffffff;">OK</span>
</div>
</div>
<div id="twin-caption">Synthetic demo | <span id="disclaimer-text"></span></div>
</div>

<script>
(function() {
function showError(msg) {
    var fb = document.getElementById("error-fallback");
    var ed = document.getElementById("error-details");
    if (fb) {
        fb.style.display = "block";
        if (ed && msg) {
            ed.textContent = String(msg);
        }
    }
}

if (typeof THREE === "undefined" || typeof THREE.OrbitControls === "undefined") {
    showError("3D view unavailable (WebGL or network). The 2D twin below still works.");
    return;
}

try {
    var PAYLOAD = __PAYLOAD_JSON__;
    var acBadge = document.getElementById("ac-badge");
    if (acBadge && PAYLOAD.aircraft_id) {
        acBadge.textContent = PAYLOAD.aircraft_id;
    }
    var discl = document.getElementById("disclaimer-text");
    if (discl && PAYLOAD.disclaimer) {
        discl.textContent = PAYLOAD.disclaimer;
    }

    var e1 = PAYLOAD.engine1 || {};
    var cycles = e1.cycles || [1];
    var dates = e1.dates || [""];
    var ruls = e1.rul || [0];
    var risks = e1.risk || ["green"];
    var statuses = e1.status || ["OK"];
    var wears = e1.wear || { fan: [0], compressor: [0], combustor: [0], turbine: [0] };
    var maxIndex = Math.max(0, cycles.length - 1);
    var currentIndex = 0;
    var isPlaying = false;
    var currentSpeedMultiplier = 1;
    var labelsVisible = true;
    var viewMode = "condition";

    var slider = document.getElementById("cycle-slider");
    slider.min = "0";
    slider.max = String(maxIndex);
    slider.value = "0";

    function getWearColor(wear) {
        var w = Math.max(0.0, Math.min(100.0, Number(wear) || 0.0));
        var cGreen = new THREE.Color(0x16a34a);
        var cAmber = new THREE.Color(0xd97706);
        var cRed = new THREE.Color(0xdc2626);
        var col = new THREE.Color();
        if (w < 40.0) {
            var t = w / 40.0;
            col.copy(cGreen).lerp(cAmber, t * 0.25);
        } else if (w <= 70.0) {
            var t = (w - 40.0) / 30.0;
            var startC = cGreen.clone().lerp(cAmber, 0.25);
            col.copy(startC).lerp(cAmber, t);
        } else {
            var t = (w - 70.0) / 30.0;
            col.copy(cAmber).lerp(cRed, t);
        }
        return col;
    }

    function getStatusStyle(st) {
        var s = String(st || "").toUpperCase();
        if (s.indexOf("CANNOT") !== -1) {
            return { bg: "#991b1b", text: "#ffffff" };
        } else if (s.indexOf("ORDER") !== -1) {
            return { bg: "#ea580c", text: "#ffffff" };
        } else if (s.indexOf("WATCH") !== -1) {
            return { bg: "#d97706", text: "#ffffff" };
        } else {
            return { bg: "#16a34a", text: "#ffffff" };
        }
    }

    var container = document.getElementById("canvas-container");
    var w = container.clientWidth || window.innerWidth;
    var h = container.clientHeight || 560;

    var scene = new THREE.Scene();
    scene.background = new THREE.Color(0xeef2f6);

    var camera = new THREE.PerspectiveCamera(40, w / h, 0.1, 100);
    camera.position.set(11, 7, 13);

    var renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
    renderer.setSize(w, h);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    container.appendChild(renderer.domElement);

    var controls = new THREE.OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.05;
    controls.target.set(0, 0, 0);

    var ambLight = new THREE.AmbientLight(0xffffff, 0.7);
    scene.add(ambLight);

    var dirLight = new THREE.DirectionalLight(0xffffff, 0.75);
    dirLight.position.set(12, 18, 15);
    dirLight.castShadow = true;
    dirLight.shadow.mapSize.width = 1024;
    dirLight.shadow.mapSize.height = 1024;
    dirLight.shadow.camera.near = 1;
    dirLight.shadow.camera.far = 45;
    dirLight.shadow.camera.left = -14;
    dirLight.shadow.camera.right = 14;
    dirLight.shadow.camera.top = 14;
    dirLight.shadow.camera.bottom = -14;
    dirLight.shadow.bias = -0.0005;
    scene.add(dirLight);

    var dirLight2 = new THREE.DirectionalLight(0x94a3b8, 0.3);
    dirLight2.position.set(-10, -5, -10);
    scene.add(dirLight2);

    var floorGeo = new THREE.CylinderGeometry(14, 14, 0.1, 64);
    var floorMat = new THREE.MeshStandardMaterial({ color: 0xdbeafe, roughness: 0.9, metalness: 0.05 });
    var floorMesh = new THREE.Mesh(floorGeo, floorMat);
    floorMesh.position.set(0, -3.2, 0);
    floorMesh.receiveShadow = true;
    scene.add(floorMesh);

    var aircraftGroup = new THREE.Group();
    var bodyMat = new THREE.MeshStandardMaterial({ color: 0x94a3b8, roughness: 0.4, metalness: 0.3, transparent: true, opacity: 0.55 });

    var fuseGeo = new THREE.CylinderGeometry(1.0, 0.95, 8.5, 32);
    var fuseMesh = new THREE.Mesh(fuseGeo, bodyMat);
    fuseMesh.rotation.x = Math.PI / 2;
    fuseMesh.position.set(0, 0, -0.2);
    fuseMesh.castShadow = true;
    fuseMesh.receiveShadow = true;
    aircraftGroup.add(fuseMesh);

    var noseGeo = new THREE.ConeGeometry(1.0, 3.2, 32);
    var noseMesh = new THREE.Mesh(noseGeo, bodyMat);
    noseMesh.rotation.x = Math.PI / 2;
    noseMesh.position.set(0, 0, 5.65);
    noseMesh.castShadow = true;
    noseMesh.receiveShadow = true;
    aircraftGroup.add(noseMesh);

    var canopyGeo = new THREE.SphereGeometry(0.7, 24, 16);
    canopyGeo.scale(0.75, 0.65, 2.0);
    var canopyMat = new THREE.MeshStandardMaterial({ color: 0x1e293b, roughness: 0.2, metalness: 0.8, transparent: true, opacity: 0.7 });
    var canopyMesh = new THREE.Mesh(canopyGeo, canopyMat);
    canopyMesh.position.set(0, 0.85, 1.8);
    canopyMesh.castShadow = true;
    aircraftGroup.add(canopyMesh);

    var wingGeo = new THREE.BoxGeometry(6.2, 0.14, 2.6);
    var leftWing = new THREE.Mesh(wingGeo, bodyMat);
    leftWing.position.set(-4.2, -0.15, -0.8);
    leftWing.rotation.y = -0.26;
    leftWing.castShadow = true;
    leftWing.receiveShadow = true;
    aircraftGroup.add(leftWing);

    var rightWing = new THREE.Mesh(wingGeo, bodyMat);
    rightWing.position.set(4.2, -0.15, -0.8);
    rightWing.rotation.y = 0.26;
    rightWing.castShadow = true;
    rightWing.receiveShadow = true;
    aircraftGroup.add(rightWing);

    var finGeo = new THREE.BoxGeometry(0.12, 2.0, 1.6);
    var leftFin = new THREE.Mesh(finGeo, bodyMat);
    leftFin.position.set(-1.0, 1.35, -3.8);
    leftFin.rotation.z = 0.22;
    leftFin.rotation.x = -0.2;
    leftFin.castShadow = true;
    leftFin.receiveShadow = true;
    aircraftGroup.add(leftFin);

    var rightFin = new THREE.Mesh(finGeo, bodyMat);
    rightFin.position.set(1.0, 1.35, -3.8);
    rightFin.rotation.z = -0.22;
    rightFin.rotation.x = -0.2;
    rightFin.castShadow = true;
    rightFin.receiveShadow = true;
    aircraftGroup.add(rightFin);

    var e1Materials = {};
    var e1Meshes = {};
    var e2Materials = {};
    var e2Meshes = {};
    var intakeMat = new THREE.MeshStandardMaterial({ color: 0x475569, roughness: 0.3, metalness: 0.7 });

    function buildEngine(xPos, isLeft) {
        var engGroup = new THREE.Group();
        engGroup.position.set(xPos, -0.3, 0);

        var ringGeo = new THREE.CylinderGeometry(0.88, 0.88, 0.22, 32);
        var ringMesh = new THREE.Mesh(ringGeo, intakeMat);
        ringMesh.rotation.x = Math.PI / 2;
        ringMesh.position.set(0, 0, 2.1);
        ringMesh.castShadow = true;
        engGroup.add(ringMesh);

        var fanGeo = new THREE.CylinderGeometry(0.82, 0.80, 1.0, 32);
        var fanMat = new THREE.MeshStandardMaterial({ color: 0x16a34a, roughness: 0.35, metalness: 0.45 });
        var fanMesh = new THREE.Mesh(fanGeo, fanMat);
        fanMesh.rotation.x = Math.PI / 2;
        fanMesh.position.set(0, 0, 1.45);
        fanMesh.castShadow = true;
        engGroup.add(fanMesh);

        var compGeo = new THREE.CylinderGeometry(0.78, 0.75, 1.3, 32);
        var compMat = new THREE.MeshStandardMaterial({ color: 0x16a34a, roughness: 0.35, metalness: 0.45 });
        var compMesh = new THREE.Mesh(compGeo, compMat);
        compMesh.rotation.x = Math.PI / 2;
        compMesh.position.set(0, 0, 0.3);
        compMesh.castShadow = true;
        engGroup.add(compMesh);

        var combGeo = new THREE.CylinderGeometry(0.74, 0.71, 1.0, 32);
        var combMat = new THREE.MeshStandardMaterial({ color: 0x16a34a, roughness: 0.35, metalness: 0.45 });
        var combMesh = new THREE.Mesh(combGeo, combMat);
        combMesh.rotation.x = Math.PI / 2;
        combMesh.position.set(0, 0, -0.85);
        combMesh.castShadow = true;
        engGroup.add(combMesh);

        var turbGeo = new THREE.CylinderGeometry(0.70, 0.66, 1.2, 32);
        var turbMat = new THREE.MeshStandardMaterial({ color: 0x16a34a, roughness: 0.35, metalness: 0.45 });
        var turbMesh = new THREE.Mesh(turbGeo, turbMat);
        turbMesh.rotation.x = Math.PI / 2;
        turbMesh.position.set(0, 0, -1.95);
        turbMesh.castShadow = true;
        engGroup.add(turbMesh);

        aircraftGroup.add(engGroup);

        if (isLeft) {
            e1Materials = { fan: fanMat, compressor: compMat, combustor: combMat, turbine: turbMat };
            e1Meshes = { fan: fanMesh, compressor: compMesh, combustor: combMesh, turbine: turbMesh };
        } else {
            e2Materials = { fan: fanMat, compressor: compMat, combustor: combMat, turbine: turbMat };
            e2Meshes = { fan: fanMesh, compressor: compMesh, combustor: combMesh, turbine: turbMesh };
        }
    }

    buildEngine(-2.2, true);
    buildEngine(2.2, false);
    scene.add(aircraftGroup);

    var e2 = PAYLOAD.engine2 || {};
    var e2Wear = e2.wear || { fan: 0, compressor: 0, combustor: 0, turbine: 0 };
    e2Materials.fan.color.copy(getWearColor(e2Wear.fan));
    e2Materials.compressor.color.copy(getWearColor(e2Wear.compressor));
    e2Materials.combustor.color.copy(getWearColor(e2Wear.combustor));
    e2Materials.turbine.color.copy(getWearColor(e2Wear.turbine));

    function applyCycle(idx) {
        if (idx < 0) idx = 0;
        if (idx > maxIndex) idx = maxIndex;
        currentIndex = idx;

        var fw = wears.fan[idx] != null ? wears.fan[idx] : 0;
        var cpw = wears.compressor[idx] != null ? wears.compressor[idx] : 0;
        var cbw = wears.combustor[idx] != null ? wears.combustor[idx] : 0;
        var tw = wears.turbine[idx] != null ? wears.turbine[idx] : 0;

        e1Materials.fan.color.copy(getWearColor(fw));
        e1Materials.compressor.color.copy(getWearColor(cpw));
        e1Materials.combustor.color.copy(getWearColor(cbw));
        e1Materials.turbine.color.copy(getWearColor(tw));

        var lFan = document.getElementById("lbl-fan");
        if (lFan) lFan.textContent = "Fan wear " + Number(fw).toFixed(1) + "%";
        var lComp = document.getElementById("lbl-comp");
        if (lComp) lComp.textContent = "Compressor wear " + Number(cpw).toFixed(1) + "%";
        var lComb = document.getElementById("lbl-comb");
        if (lComb) lComb.textContent = "Combustor wear " + Number(cbw).toFixed(1) + "%";
        var lTurb = document.getElementById("lbl-turb");
        if (lTurb) lTurb.textContent = "Turbine wear " + Number(tw).toFixed(1) + "%";

        slider.value = String(idx);
        var curC = cycles[idx] != null ? cycles[idx] : 1;
        var maxC = cycles[maxIndex] != null ? cycles[maxIndex] : 1;
        var dC = document.getElementById("disp-cycle");
        if (dC) dC.textContent = "Cycle " + curC + " / " + maxC;
        var dD = document.getElementById("disp-date");
        if (dD) dD.textContent = dates[idx] != null ? dates[idx] : "";

        var st = statuses[idx] != null ? statuses[idx] : "OK";
        var stElem = document.getElementById("disp-status");
        if (stElem) {
            stElem.textContent = st;
            var stStyle = getStatusStyle(st);
            stElem.style.background = stStyle.bg;
            stElem.style.color = stStyle.text;
        }
    }

    applyCycle(0);

    var labelTrackers = [
        { mesh: e1Meshes.fan, elem: document.getElementById("lbl-fan"), offsetY: 1.1, offsetX: -0.2 },
        { mesh: e1Meshes.compressor, elem: document.getElementById("lbl-comp"), offsetY: 1.1, offsetX: -0.2 },
        { mesh: e1Meshes.combustor, elem: document.getElementById("lbl-comb"), offsetY: 1.1, offsetX: -0.2 },
        { mesh: e1Meshes.turbine, elem: document.getElementById("lbl-turb"), offsetY: 1.1, offsetX: -0.2 },
        { mesh: e2Meshes.compressor, elem: document.getElementById("lbl-eng2"), offsetY: 1.2, offsetX: 0.3 }
    ];

    function updateLabels() {
        if (!labelsVisible) return;
        var curW = container.clientWidth || window.innerWidth;
        var curH = container.clientHeight || 560;
        var halfW = curW / 2;
        var halfH = curH / 2;
        var tempV = new THREE.Vector3();

        for (var i = 0; i < labelTrackers.length; i++) {
            var item = labelTrackers[i];
            if (!item.mesh || !item.elem) continue;
            item.mesh.getWorldPosition(tempV);
            tempV.y += item.offsetY;
            tempV.x += item.offsetX;
            tempV.project(camera);

            if (tempV.z > 1) {
                item.elem.style.display = "none";
                continue;
            }
            item.elem.style.display = "block";
            var x = (tempV.x * halfW) + halfW;
            var y = -(tempV.y * halfH) + halfH;
            item.elem.style.left = Math.round(x) + "px";
            item.elem.style.top = Math.round(y) + "px";
        }
    }

    var btnCondition = document.getElementById("btn-condition");
    var btnXray = document.getElementById("btn-xray");
    if (btnCondition && btnXray) {
        btnCondition.addEventListener("click", function() {
            viewMode = "condition";
            bodyMat.opacity = 0.55;
            bodyMat.transparent = true;
            btnCondition.classList.add("active");
            btnXray.classList.remove("active");
        });
        btnXray.addEventListener("click", function() {
            viewMode = "xray";
            bodyMat.opacity = 0.08;
            bodyMat.transparent = true;
            btnXray.classList.add("active");
            btnCondition.classList.remove("active");
        });
    }

    var btnAlerts = document.getElementById("btn-alerts");
    if (btnAlerts) {
        btnAlerts.addEventListener("click", function() {
            labelsVisible = !labelsVisible;
            var layer = document.getElementById("labels-layer");
            if (layer) layer.style.display = labelsVisible ? "block" : "none";
            btnAlerts.classList.toggle("active", labelsVisible);
        });
    }

    var btnReset = document.getElementById("btn-reset");
    if (btnReset) {
        btnReset.addEventListener("click", function() {
            camera.position.set(11, 7, 13);
            controls.target.set(0, 0, 0);
            controls.update();
        });
    }

    var btnPlay = document.getElementById("btn-play");
    if (btnPlay) {
        btnPlay.addEventListener("click", function() {
            if (!isPlaying) {
                if (currentIndex >= maxIndex) {
                    currentIndex = 0;
                    applyCycle(currentIndex);
                }
                isPlaying = true;
                btnPlay.textContent = "Pause";
                lastTickTime = performance.now();
            } else {
                isPlaying = false;
                btnPlay.textContent = "Play";
            }
        });
    }

    slider.addEventListener("input", function() {
        var val = parseInt(this.value, 10);
        applyCycle(val);
    });

    var speeds = [1, 3, 8];
    speeds.forEach(function(s) {
        var b = document.getElementById("btn-spd-" + s);
        if (b) {
            b.addEventListener("click", function() {
                currentSpeedMultiplier = s;
                speeds.forEach(function(o) {
                    var ob = document.getElementById("btn-spd-" + o);
                    if (ob) ob.classList.toggle("active", o === s);
                });
            });
        }
    });

    function onWindowResize() {
        var rw = container.clientWidth || window.innerWidth;
        var rh = container.clientHeight || 560;
        camera.aspect = rw / rh;
        camera.updateProjectionMatrix();
        renderer.setSize(rw, rh);
    }
    window.addEventListener("resize", onWindowResize);

    var lastTickTime = performance.now();
    function animate(now) {
        requestAnimationFrame(animate);
        if (isPlaying && maxIndex > 0) {
            var interval = 1000.0 / (5.0 * currentSpeedMultiplier);
            var delta = now - lastTickTime;
            if (delta >= interval) {
                lastTickTime = now - (delta % interval);
                if (currentIndex < maxIndex) {
                    currentIndex++;
                    applyCycle(currentIndex);
                    if (currentIndex >= maxIndex) {
                        isPlaying = false;
                        if (btnPlay) btnPlay.textContent = "Play";
                    }
                }
            }
        }
        controls.update();
        if (labelsVisible) {
            updateLabels();
        }
        renderer.render(scene, camera);
    }
    requestAnimationFrame(animate);

} catch (err) {
    showError(err && err.message ? err.message : err);
}
})();
</script>
</body>
</html>"""


def render_twin3d_html(payload: Dict[str, Any]) -> str:
    """Render a standalone, self-contained Three.js 3D visualization HTML page.

    Embeds Three.js r128 and OrbitControls from jsDelivr CDN, constructs a 3D jet
    scene with dual engines using 3D primitives, and provides interactive playback,
    inspection modes (Condition, X-ray), and HUD telemetry labels.

    Args:
        payload: Dict conforming to the twin payload schema.

    Returns:
        Self-contained HTML document string with inline CSS and JS.
    """
    safe_payload = json.dumps(payload, ensure_ascii=True).replace("</", r"<\/")
    return TWIN3D_HTML_TEMPLATE.replace("__PAYLOAD_JSON__", safe_payload)
