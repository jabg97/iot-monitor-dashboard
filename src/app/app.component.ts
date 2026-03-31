import { Component, OnInit } from '@angular/core'
import { Router } from '@angular/router'
import { AzureService } from 'src/services/azure.service'

@Component({
  selector: 'app-root',
  templateUrl: './app.component.html',
  styleUrls: ['./app.component.scss'],
})
export class AppComponent implements OnInit {

  constructor(private azureService: AzureService, private router: Router) {}

  ngOnInit(): void {
    // Redirect to login if session is expired or absent
    if (!this.azureService.isAuthenticated()) {
      this.router.navigate(['/login'])
    }
  }

  logOut() {
    if (confirm('Are you sure you want to log out?')) {
      this.azureService.logout()
    }
  }
}
