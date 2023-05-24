import { Pipe, PipeTransform } from '@angular/core';

@Pipe({
  name: 'count',
})
export class CountPipe implements PipeTransform {
  transform(length: number, singular: string, plural: string): string {
    return length == 1 ? `A ${singular}` : `(${length}) ${plural}`;
  }
}
