"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { FormEvent, useEffect, useRef, useState } from "react";
import { BellIcon, CameraIcon, SunIcon } from "@phosphor-icons/react";
import { apiClient, type GardenPlant, type LightClassification, type LightMeasurementCreate, type MeasurementReliability, type MeasurementSource } from "@/lib/api/client";
import { Button, Card, Chip, Notice, PageHeader, SelectField } from "@/components/ui";
import iconStyles from "@/components/ui/Icons.module.scss";
import styles from "./LightMeter.module.scss";

type SensorReading = {
  source: MeasurementSource;
  classification: LightClassification;
  reliability: MeasurementReliability;
  lux: number | null;
  copy: string;
  metadata: Record<string, unknown>;
};

type AmbientLightSensorConstructor = new () => {
  illuminance: number | null;
  start: () => void;
  stop: () => void;
  addEventListener: (type: "reading" | "error", listener: () => void, options?: AddEventListenerOptions) => void;
};

const manualOptions: Array<{ value: LightClassification; label: string; copy: string }> = [
  { value: "baja", label: "Baja", copy: "Sombra marcada o una habitacion oscura." },
  { value: "media", label: "Media", copy: "Luz ambiente clara sin sol directo." },
  { value: "alta", label: "Alta", copy: "Muy iluminado cerca de una ventana." },
  { value: "directa", label: "Directa", copy: "Rayos de sol llegan a la planta." },
];

const reliabilityTone: Record<MeasurementReliability, "success" | "warning" | "error"> = {
  high: "success",
  medium: "warning",
  low: "error",
};

const reliabilityChipLabel: Record<MeasurementReliability, string> = {
  high: "Confiabilidad alta",
  medium: "Confiabilidad media",
  low: "Confiabilidad baja",
};

const sourceChipLabel: Record<MeasurementSource, string> = {
  sensor: "Sensor ambiental",
  camera: "Camara aproximada",
  manual: "Registro manual",
};

export function LightMeter() {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const [reading, setReading] = useState<SensorReading | null>(null);
  const [selectedPlantId, setSelectedPlantId] = useState("");
  const [manualClassification, setManualClassification] = useState<LightClassification>("media");
  const [status, setStatus] = useState("Listo para medir con el mejor metodo disponible.");
  const [error, setError] = useState<string | null>(null);
  const [cameraActive, setCameraActive] = useState(false);

  const garden = useQuery({ queryKey: ["garden", "list", ""], queryFn: () => apiClient.listGardenPlants() });
  const saveMeasurement = useMutation({ mutationFn: (body: LightMeasurementCreate) => apiClient.createLightMeasurement(body) });

  useEffect(() => () => stopCamera(false), []);

  async function measureAutomatically() {
    setError(null);
    saveMeasurement.reset();
    setStatus("Buscando sensor de luz ambiental...");
    const sensorReading = await readAmbientLightSensor();
    if (sensorReading) {
      setReading(sensorReading);
      setStatus("Medicion por sensor completada.");
      return;
    }
    setStatus("El sensor no esta disponible. Probando estimacion aproximada con camara...");
    await startCamera();
  }

  async function readAmbientLightSensor(): Promise<SensorReading | null> {
    const Sensor = (window as typeof window & { AmbientLightSensor?: AmbientLightSensorConstructor }).AmbientLightSensor;
    if (!Sensor) return null;

    try {
      const permissions = navigator.permissions as Permissions | undefined;
      if (permissions?.query) {
        const permission = await permissions.query({ name: "ambient-light-sensor" as PermissionName });
        if (permission.state === "denied") return null;
      }

      return await new Promise((resolve) => {
        const sensor = new Sensor();
        const timeout = window.setTimeout(() => {
          sensor.stop();
          resolve(null);
        }, 3500);
        sensor.addEventListener("reading", () => {
          window.clearTimeout(timeout);
          sensor.stop();
          const lux = Math.max(0, Number(sensor.illuminance ?? 0));
          resolve({
            source: "sensor",
            lux,
            classification: classifyLux(lux),
            reliability: "high",
            copy: "Lectura directa del sensor de luz ambiental del dispositivo.",
            metadata: { permission: "granted" },
          });
        }, { once: true });
        sensor.addEventListener("error", () => {
          window.clearTimeout(timeout);
          sensor.stop();
          resolve(null);
        }, { once: true });
        sensor.start();
      });
    } catch {
      return null;
    }
  }

  async function startCamera() {
    if (!navigator.mediaDevices?.getUserMedia) {
      setStatus("Tu navegador no permite usar camara desde esta pantalla. Usa registro manual.");
      return;
    }

    try {
      stopCamera();
      const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" } });
      streamRef.current = stream;
      setCameraActive(true);
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }
      setStatus("Camara activa. Apunta hacia donde recibe luz la planta y toma una medicion aproximada.");
    } catch {
      setStatus("No tenemos permiso de camara. Usa registro manual.");
    }
  }

  function stopCamera(updateState = true) {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    if (updateState) setCameraActive(false);
  }

  function captureCameraReading() {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    const context = canvas?.getContext("2d", { willReadFrequently: true });
    if (!video || !canvas || !context || video.videoWidth === 0 || video.videoHeight === 0) {
      setError("No pudimos leer la imagen de camara. Reintenta o registra manualmente.");
      return;
    }

    const samples = Array.from({ length: 4 }, () => sampleVideoLuminance(video, canvas, context));
    const averages = samples.map((sample) => sample.average);
    const average = mean(averages);
    const betweenFrames = standardDeviation(averages);
    const withinFrame = mean(samples.map((sample) => sample.deviation));
    const unreliableReason = cameraUnreliableReason(average, withinFrame, betweenFrames);
    const lux = Math.round(estimateLuxFromLuminance(average));
    const reliability: MeasurementReliability = unreliableReason ? "low" : "medium";

    setReading({
      source: "camera",
      lux,
      classification: classifyLux(lux),
      reliability,
      copy: unreliableReason
        ? `Medicion aproximada no confiable: ${unreliableReason}. Repeti apuntando a la zona iluminada de la planta.`
        : "Medicion aproximada calculada desde luminancia de camara; no equivale a un luxometro profesional.",
      metadata: { averageLuminance: average, frameDeviation: withinFrame, sampleDeviation: betweenFrames, unreliableReason },
    });
    setStatus(unreliableReason ? "La medicion de camara necesita repetirse." : "Medicion aproximada por camara completada.");
  }

  function registerManual(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const option = manualOptions.find((item) => item.value === manualClassification);
    setReading({
      source: "manual",
      lux: null,
      classification: manualClassification,
      reliability: "low",
      copy: `Registro manual: ${option?.copy ?? "condicion indicada por la persona usuaria"}`,
      metadata: { manualLabel: option?.label },
    });
    setStatus("Registro manual preparado para guardar.");
  }

  async function persistReading() {
    if (!reading) return;
    await saveMeasurement.mutateAsync({
      garden_plant_id: selectedPlantId || null,
      classification: reading.classification,
      lux: reading.lux,
      reliability: reading.reliability,
      source: reading.source,
      metadata: reading.metadata,
    });
  }

  const plants = garden.data ?? [];
  const unreliableCamera = reading?.reliability === "low" && reading.source === "camera";
  const cameraSupported = typeof navigator !== "undefined" && Boolean(navigator.mediaDevices?.getUserMedia);
  const sensorSupported = typeof window !== "undefined" && Boolean((window as typeof window & { AmbientLightSensor?: unknown }).AmbientLightSensor);

  return (
    <section className={styles.page}>
      <PageHeader
        eyebrow="Cuidados"
        heading="Medidor de luz"
        description="Mediciones reales cuando se pueda, alternativas claras cuando no."
      />

      <p className={styles.introBody}>
        Primero intentamos sensor ambiental, luego camara aproximada y finalmente registro manual.
      </p>

      {error ? (
        <Notice tone="error" role="alert">{error}</Notice>
      ) : null}
      {saveMeasurement.isError ? (
        <Notice tone="error" role="alert">{saveMeasurement.error.message || "No pudimos guardar la medicion."}</Notice>
      ) : null}
      {saveMeasurement.isSuccess ? (
        <Notice tone="success" role="status">Medicion guardada correctamente.</Notice>
      ) : null}
      <Notice tone="info" role="status">
        {status}
      </Notice>

      <div className={styles.layout}>
        <div className={styles.primaryColumn}>
          <Card variant="tonal" padding="md" className={styles.measureCard}>
            <h2 className={styles.measureHeading}>Medicion principal</h2>
            <p className={styles.measureCopy}>
              Proba primero el sensor ambiental del dispositivo. Si no esta disponible, pasamos automaticamente a la camara.
            </p>
            <div className={styles.measureActions}>
              <Button type="button" variant="primary" size="md" onClick={measureAutomatically} leadingIcon={<SunIcon aria-hidden="true" size="1rem" className={iconStyles.toneOnPrimary} />}>
                Medir luz
              </Button>
              <Button type="button" variant="outline" size="md" onClick={startCamera} leadingIcon={<CameraIcon aria-hidden="true" size="1rem" className={iconStyles.tonePrimary} />}>
                Usar camara
              </Button>
            </div>
            <ul className={styles.sensorStatusList}>
              <li className={styles.sensorStatusItem}>
                <span className={styles.sensorDot} data-state={sensorSupported ? "ready" : "blocked"} />
                Sensor ambiental {sensorSupported ? "disponible" : "no disponible en este navegador"}
              </li>
              <li className={styles.sensorStatusItem}>
                <span className={styles.sensorDot} data-state={cameraSupported ? "ready" : "blocked"} />
                Camara {cameraSupported ? "lista para usar" : "no disponible en este navegador"}
              </li>
              <li className={styles.sensorStatusItem}>
                <span className={styles.sensorDot} data-state={cameraActive ? "active" : "ready"} />
                Camara {cameraActive ? "capturando" : "inactiva"}
              </li>
            </ul>
          </Card>

          <Card className={styles.cameraCard} data-active={cameraActive} aria-live="polite">
            <h2 className={styles.measureHeading}>Estimacion con camara</h2>
            <p className={styles.measureCopy}>
              Apunta hacia donde recibe luz la planta y captura una muestra estable. Si la camara queda cubierta, sobreexpuesta o las muestras son inconsistentes, te avisaremos para repetir.
            </p>
            <video ref={videoRef} playsInline muted aria-label="Vista de camara para estimar luz" className={styles.cameraVideo} />
            <canvas ref={canvasRef} width={96} height={96} hidden />
            <div className={styles.cameraActions}>
              <Button type="button" variant="primary" size="md" onClick={captureCameraReading} disabled={!cameraActive}>
                Tomar medicion aproximada
              </Button>
              <Button type="button" variant="ghost" size="md" onClick={() => stopCamera(true)} disabled={!cameraActive}>
                Detener camara
              </Button>
            </div>
          </Card>

          {reading ? (
            <Card className={styles.resultCard} aria-labelledby="light-meter-result-heading">
              <p className={styles.resultEyebrow}>
                <Chip tone="primary" icon={<SunIcon aria-hidden="true" size="1rem" className={iconStyles.toneOnPrimary} />}>
                  {sourceChipLabel[reading.source]}
                </Chip>
                <Chip tone={reliabilityTone[reading.reliability]} icon={<BellIcon aria-hidden="true" size="1rem" className={iconStyles.tonePrimary} />}>
                  {reliabilityChipLabel[reading.reliability]}
                </Chip>
              </p>
              <h2 id="light-meter-result-heading" className={styles.resultHeading}>
                {classificationLabel(reading.classification)}
              </h2>
              <p className={styles.resultLux}>
                {reading.lux === null ? "Sin lux estimado." : `${Math.round(reading.lux)} lux estimados.`}
              </p>
              <p className={styles.resultCopy}>{reading.copy}</p>
              {unreliableCamera ? (
                <p className={styles.resultCopy} role="alert">
                  Repeti la medicion antes de guardarla o usa registro manual.
                </p>
              ) : null}
            </Card>
          ) : null}
        </div>

        <div className={styles.asideColumn}>
          <Card variant="tonal" padding="md" className={styles.manualCard}>
            <h2 className={styles.measureHeading}>Registro manual</h2>
            <form className={styles.manualForm} onSubmit={registerManual}>
              <SelectField
                kind="select"
                label="Condicion observada"
                value={manualClassification}
                onChange={(event) => setManualClassification(event.target.value as LightClassification)}
              >
                {manualOptions.map((option) => (
                  <option key={option.value} value={option.value}>{option.label} - {option.copy}</option>
                ))}
              </SelectField>
              <div className={styles.manualActions}>
                <Button type="submit" variant="tertiary" size="md" fullWidth>
                  Usar registro manual
                </Button>
              </div>
            </form>
          </Card>

          <Card variant="tonal" padding="md" className={styles.association}>
            <h2 className={styles.measureHeading}>Guardar medicion</h2>
            <p className={styles.associationHint}>
              Asocia la lectura a una planta de Mi Jardin para usarla como contexto en sus cuidados. Podes guardar sin asociar.
            </p>
            <SelectField
              kind="select"
              label="Asociar a planta de Mi Jardin (opcional)"
              value={selectedPlantId}
              onChange={(event) => setSelectedPlantId(event.target.value)}
            >
              <option value="">Sin asociar</option>
              {plants.map((plant) => (
                <option key={plant.id} value={plant.id}>{plantLabel(plant)}</option>
              ))}
            </SelectField>
            {garden.isError ? (
              <Notice tone="error" role="alert">No pudimos cargar Mi Jardin. Podes guardar sin asociar.</Notice>
            ) : null}
            <div className={styles.manualActions}>
              <Button
                type="button"
                variant="primary"
                size="md"
                fullWidth
                onClick={persistReading}
                disabled={!reading || saveMeasurement.isPending || Boolean(unreliableCamera)}
              >
                {saveMeasurement.isPending ? "Guardando..." : "Guardar medicion"}
              </Button>
            </div>
          </Card>
        </div>
      </div>
    </section>
  );
}

function sampleVideoLuminance(video: HTMLVideoElement, canvas: HTMLCanvasElement, context: CanvasRenderingContext2D) {
  context.drawImage(video, 0, 0, canvas.width, canvas.height);
  const data = context.getImageData(0, 0, canvas.width, canvas.height).data;
  const values: number[] = [];
  for (let index = 0; index < data.length; index += 16) {
    values.push(0.2126 * data[index] + 0.7152 * data[index + 1] + 0.0722 * data[index + 2]);
  }
  return { average: mean(values), deviation: standardDeviation(values) };
}

function classifyLux(lux: number): LightClassification {
  if (lux >= 20_000) return "directa";
  if (lux >= 3_000) return "alta";
  if (lux >= 500) return "media";
  return "baja";
}

function estimateLuxFromLuminance(luminance: number) {
  return Math.max(0, (luminance / 255) ** 2.2 * 35_000);
}

function cameraUnreliableReason(average: number, withinFrame: number, betweenFrames: number) {
  if (average < 8 || withinFrame < 2) return "imagen cubierta o demasiado oscura";
  if (average > 247) return "imagen sobreexpuesta";
  if (betweenFrames > 45) return "lecturas inconsistentes entre muestras";
  return null;
}

function mean(values: number[]) {
  return values.reduce((total, value) => total + value, 0) / Math.max(values.length, 1);
}

function standardDeviation(values: number[]) {
  const average = mean(values);
  return Math.sqrt(mean(values.map((value) => (value - average) ** 2)));
}

function classificationLabel(value: LightClassification) {
  return { baja: "Luz baja", media: "Luz media", alta: "Luz alta", directa: "Luz directa" }[value];
}

function plantLabel(plant: GardenPlant) {
  return plant.nickname ?? plant.profile.selected_alias ?? plant.profile.common_name ?? plant.profile.scientific_name;
}
