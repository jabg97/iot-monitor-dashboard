export interface ClimateVariables {
  currentAirTemperature: number;
  currentHumidity: number;
  currentSoilMoisture: number;
}

export interface ClimateRange {
  minAirTemperature: number;
  maxAirTemperature: number;
  minHumidity: number;
  maxHumidity: number;
  minSoilMoisture: number;
  maxSoilMoisture: number;
}