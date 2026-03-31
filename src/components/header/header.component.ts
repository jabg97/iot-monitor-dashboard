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

  readonly title = 'IoT Monitor';

  user = '';
  isMenuOpen = false;

  constructor(public router: Router, private azureService: AzureService) {
    this.user = azureService.getUserName();
  }

  toggleMenu(): void {
    this.isMenuOpen = !this.isMenuOpen;
  }

  logOut(): void {
    this.close.emit();
  }
}
