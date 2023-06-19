import { Component, EventEmitter, Output } from '@angular/core';
import { Router } from '@angular/router';
import { AzureService } from 'src/services/azure.service';

@Component({
  selector: 'app-header',
  templateUrl: './header.component.html',
  styleUrls: ['./header.component.scss'],
})
export class HeaderComponent {

  @Output()
  close = new EventEmitter<void>();
  
  title = 'IoT Monitor';

  user = '';

  constructor(public router: Router, private azureService: AzureService) {
    this.user = azureService.getUserName();
  }
  logOut() {
    this.close.emit();
  }
}
