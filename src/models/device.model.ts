import { ClimateRange, ClimateVariables } from "./climate.model";

export interface Device {
  id: string;
  name?: string | null;
  userId?: string | null;
  cropId?: string | null;
  range?: ClimateRange | null;
  sensor?: ClimateVariables | null;
}