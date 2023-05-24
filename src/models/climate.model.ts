export interface ClimateVariables {
  currentAirTemperature: number;
  currentAirHumidity: number;
  currentSoilMoisture: number;
}

export interface ClimateRange {
  minAirTemperature: number;
  maxAirTemperature: number;
  minAirHumidity: number;
  maxAirHumidity: number;
  minSoilMoisture: number;
  maxSoilMoisture: number;
}

export enum ClimateRangeLimit {
  MIN = -100,
  ONE = 1,
  MAX = 100,
}
