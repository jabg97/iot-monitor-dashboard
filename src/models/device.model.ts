import { ClimateRange, ClimateVariables } from './climate.model';
import { History } from './history.model';

export interface Device {
  id: string;
  name?: string | null;
  userId?: string | null;
  cropId?: string | null;
  history?: Array<History>;
  range?: ClimateRange | null;
  sensor?: ClimateVariables | null;
}
