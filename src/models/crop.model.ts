import { ClimateRange } from "./climate.model";

export interface Crop {
  id: string;
  name: string;
  range?: ClimateRange
}