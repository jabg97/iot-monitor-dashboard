import { ClimateVariables } from './climate.model';

export interface History {
  dateTime: string;
  state: string;
  cropId?: string | null;
  sensor?: ClimateVariables | null;
}
