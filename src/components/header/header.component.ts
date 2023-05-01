import { Component, Input} from '@angular/core';

@Component({
  selector: 'app-header',
  templateUrl: './header.component.html',
  styleUrls: ['./header.component.scss']
})
export class HeaderComponent{
  
  title:string = 'IoT Monitor';

  @Input () user:string = ""; 

  constructor() {
  }
  
  logOut(){
    alert("test")
  }
}