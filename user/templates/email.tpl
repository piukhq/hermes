{% extends "mail_templated/base.tpl" %}

{% block subject %}
    Reset Bink password
{% endblock %}

{% block html %}
<head>

    <meta http-equiv="content-type" content="text/html; charset=utf-8">
  </head>
  <body bgcolor="#FFFFFF" text="#000000">

      <!-- NAME: NEW COLLECTION --><!--[if gte mso 15]>
		<xml>
			<o:OfficeDocumentSettings>
			<o:AllowPNG/>
			<o:PixelsPerInch>96</o:PixelsPerInch>
			</o:OfficeDocumentSettings>
		</xml>
		<![endif]-->
      <meta http-equiv="Content-Type" content="text/html; charset=utf-8">
      <meta http-equiv="X-UA-Compatible" content="IE=edge">
      <meta name="viewport" content="width=device-width,
        initial-scale=1">
      <title>*|MC:SUBJECT|*</title>
      <style type="text/css">
		p{
			margin:10px 0;
			padding:0;
		}
		table{
			border-collapse:collapse;
		}
		h1,h2,h3,h4,h5,h6{
			display:block;
			margin:0;
			padding:0;
		}
		img,a img{
			border:0;
			height:auto;
			outline:none;
			text-decoration:none;
		}
		body,#bodyTable,#bodyCell{
			height:100%;
			margin:0;
			padding:0;
			width:100%;
		}
		#outlook a{
			padding:0;
		}
		img{
			-ms-interpolation-mode:bicubic;
		}
		table{
			mso-table-lspace:0pt;
			mso-table-rspace:0pt;
		}
		.ReadMsgBody{
			width:100%;
		}
		.ExternalClass{
			width:100%;
		}
		p,a,li,td,blockquote{
			mso-line-height-rule:exactly;
		}
		a[href^=tel],a[href^=sms]{
			color:inherit;
			cursor:default;
			text-decoration:none;
		}
		p,a,li,td,body,table,blockquote{
			-ms-text-size-adjust:100%;
			-webkit-text-size-adjust:100%;
		}
		.ExternalClass,.ExternalClass p,.ExternalClass td,.ExternalClass div,.ExternalClass span,.ExternalClass font{
			line-height:100%;
		}
		a[x-apple-data-detectors]{
			color:inherit !important;
			text-decoration:none !important;
			font-size:inherit !important;
			font-family:inherit !important;
			font-weight:inherit !important;
			line-height:inherit !important;
		}
		.templateContainer{
			max-width:600px !important;
		}
		a.mcnButton{
			display:block;
		}
		.mcnImage{
			vertical-align:bottom;
		}
		.mcnTextContent{
			word-break:break-word;
		}
		.mcnTextContent img{
			height:auto !important;
		}
		.mcnDividerBlock{
			table-layout:fixed !important;
		}
		body,#bodyTable{
			background-color:#FFFFFF;
		}
		#bodyCell{
			border-top:0;
		}
		h1{
			color:#FFFFFF;
			font-family:Arial, 'Helvetica Neue', Helvetica, sans-serif;
			font-size:60px;
			font-style:normal;
			font-weight:normal;
			line-height:200%;
			letter-spacing:normal;
			text-align:center;
		}
		h2{
			color:#FFFFFF;
			font-family:Helvetica;
			font-size:30px;
			font-style:normal;
			font-weight:bold;
			line-height:125%;
			letter-spacing:normal;
			text-align:center;
		}
		h3{
			color:#393939;
			font-family:Helvetica;
			font-size:20px;
			font-style:normal;
			font-weight:bold;
			line-height:125%;
			letter-spacing:normal;
			text-align:left;
		}
		h4{
			color:#999999;
			font-family:Helvetica;
			font-size:18px;
			font-style:normal;
			font-weight:bold;
			line-height:125%;
			letter-spacing:normal;
			text-align:left;
		}
		#templatePreheader{
			background-color:#ffffff;
			background-image:none;
			background-repeat:no-repeat;
			background-position:center;
			background-size:cover;
			border-top:0;
			border-bottom:0;
			padding-top:9px;
			padding-bottom:9px;
		}
		#templatePreheader .mcnTextContent,#templatePreheader .mcnTextContent p{
			color:#656565;
			font-family:Helvetica;
			font-size:12px;
			line-height:150%;
			text-align:left;
		}
		#templatePreheader .mcnTextContent a,#templatePreheader .mcnTextContent p a{
			color:#656565;
			font-weight:normal;
			text-decoration:underline;
		}
		#templateHeader{
			background-color:#ffffff;
			background-image:none;
			background-repeat:no-repeat;
			background-position:center;
			background-size:cover;
			border-top:4px solid #f20060;
			border-bottom:0;
			padding-top:0px;
			padding-bottom:0px;
		}
		#templateHeader .mcnTextContent,#templateHeader .mcnTextContent p{
			color:#FFFFFF;
			font-family:Helvetica;
			font-size:20px;
			line-height:150%;
			text-align:center;
		}
		#templateHeader .mcnTextContent a,#templateHeader .mcnTextContent p a{
			color:#FFFFFF;
			font-weight:normal;
			text-decoration:underline;
		}
		#templateBody{
			background-color:#ffffff;
			background-image:none;
			background-repeat:no-repeat;
			background-position:center;
			background-size:cover;
			border-top:0;
			border-bottom:0;
			padding-top:0px;
			padding-bottom:0;
		}
		#templateBody .mcnTextContent,#templateBody .mcnTextContent p{
			color:#202020;
			font-family:Arial, 'Helvetica Neue', Helvetica, sans-serif;
			font-size:18px;
			line-height:150%;
			text-align:center;
		}
		#templateBody .mcnTextContent a,#templateBody .mcnTextContent p a{
			color:#00b9ff;
			font-weight:normal;
			text-decoration:underline;
		}
		#templateUpperColumns{
			background-color:#ffffff;
			background-image:none;
			background-repeat:no-repeat;
			background-position:center;
			background-size:cover;
			border-top:0;
			border-bottom:0;
			padding-top:0;
			padding-bottom:0px;
		}
		#templateUpperColumns .columnContainer .mcnTextContent,#templateUpperColumns .columnContainer .mcnTextContent p{
			color:#202020;
			font-family:Helvetica;
			font-size:16px;
			line-height:150%;
			text-align:left;
		}
		#templateUpperColumns .columnContainer .mcnTextContent a,#templateUpperColumns .columnContainer .mcnTextContent p a{
			color:#ED5A2E;
			font-weight:normal;
			text-decoration:underline;
		}
		#templateLowerColumns{
			background-color:#ffffff;
			background-image:none;
			background-repeat:no-repeat;
			background-position:center;
			background-size:cover;
			border-top:0;
			border-bottom:1px none ;
			padding-top:2px;
			padding-bottom:2px;
		}
		#templateLowerColumns .columnContainer .mcnTextContent,#templateLowerColumns .columnContainer .mcnTextContent p{
			color:#202020;
			font-family:Helvetica;
			font-size:16px;
			line-height:150%;
			text-align:left;
		}
		#templateLowerColumns .columnContainer .mcnTextContent a,#templateLowerColumns .columnContainer .mcnTextContent p a{
			color:#666666;
			font-weight:normal;
			text-decoration:underline;
		}
		#templateFooter{
			background-color:#ffffff;
			background-image:none;
			background-repeat:no-repeat;
			background-position:center;
			background-size:cover;
			border-top:0;
			border-bottom:0;
			padding-top:1px;
			padding-bottom:1px;
		}
		#templateFooter .mcnTextContent,#templateFooter .mcnTextContent p{
			color:#656565;
			font-family:Helvetica;
			font-size:12px;
			line-height:150%;
			text-align:left;
		}
		#templateFooter .mcnTextContent a,#templateFooter .mcnTextContent p a{
			color:#656565;
			font-weight:normal;
			text-decoration:underline;
		}
	@media only screen and (min-width:768px){
		.templateContainer{
			width:600px !important;
		}

}	@media only screen and (max-width: 480px){
		body,table,td,p,a,li,blockquote{
			-webkit-text-size-adjust:none !important;
		}

}	@media only screen and (max-width: 480px){
		body{
			width:100% !important;
			min-width:100% !important;
		}

}	@media only screen and (max-width: 480px){
		#bodyCell{
			padding-top:10px !important;
		}

}	@media only screen and (max-width: 480px){
		.columnWrapper{
			max-width:100% !important;
			width:100% !important;
		}

}	@media only screen and (max-width: 480px){
		.mcnImage{
			width:100% !important;
		}

}	@media only screen and (max-width: 480px){
		.mcnCartContainer,.mcnCaptionTopContent,.mcnRecContentContainer,.mcnCaptionBottomContent,.mcnTextContentContainer,.mcnBoxedTextContentContainer,.mcnImageGroupContentContainer,.mcnCaptionLeftTextContentContainer,.mcnCaptionRightTextContentContainer,.mcnCaptionLeftImageContentContainer,.mcnCaptionRightImageContentContainer,.mcnImageCardLeftTextContentContainer,.mcnImageCardRightTextContentContainer{
			max-width:100% !important;
			width:100% !important;
		}

}	@media only screen and (max-width: 480px){
		.mcnBoxedTextContentContainer{
			min-width:100% !important;
		}

}	@media only screen and (max-width: 480px){
		.mcnImageGroupContent{
			padding:9px !important;
		}

}	@media only screen and (max-width: 480px){
		.mcnCaptionLeftContentOuter .mcnTextContent,.mcnCaptionRightContentOuter .mcnTextContent{
			padding-top:9px !important;
		}

}	@media only screen and (max-width: 480px){
		.mcnImageCardTopImageContent,.mcnCaptionBlockInner .mcnCaptionTopContent:last-child .mcnTextContent{
			padding-top:18px !important;
		}

}	@media only screen and (max-width: 480px){
		.mcnImageCardBottomImageContent{
			padding-bottom:9px !important;
		}

}	@media only screen and (max-width: 480px){
		.mcnImageGroupBlockInner{
			padding-top:0 !important;
			padding-bottom:0 !important;
		}

}	@media only screen and (max-width: 480px){
		.mcnImageGroupBlockOuter{
			padding-top:9px !important;
			padding-bottom:9px !important;
		}

}	@media only screen and (max-width: 480px){
		.mcnTextContent,.mcnBoxedTextContentColumn{
			padding-right:18px !important;
			padding-left:18px !important;
		}

}	@media only screen and (max-width: 480px){
		.mcnImageCardLeftImageContent,.mcnImageCardRightImageContent{
			padding-right:18px !important;
			padding-bottom:0 !important;
			padding-left:18px !important;
		}

}	@media only screen and (max-width: 480px){
		.mcpreview-image-uploader{
			display:none !important;
			width:100% !important;
		}

}	@media only screen and (max-width: 480px){
		h1{
			font-size:22px !important;
			line-height:125% !important;
		}

}	@media only screen and (max-width: 480px){
		h2{
			font-size:20px !important;
			line-height:125% !important;
		}

}	@media only screen and (max-width: 480px){
		h3{
			font-size:18px !important;
			line-height:125% !important;
		}

}	@media only screen and (max-width: 480px){
		h4{
			font-size:16px !important;
			line-height:150% !important;
		}

}	@media only screen and (max-width: 480px){
		.mcnBoxedTextContentContainer .mcnTextContent,.mcnBoxedTextContentContainer .mcnTextContent p{
			font-size:14px !important;
			line-height:150% !important;
		}

}	@media only screen and (max-width: 480px){
		#templatePreheader{
			display:block !important;
		}

}	@media only screen and (max-width: 480px){
		#templatePreheader .mcnTextContent,#templatePreheader .mcnTextContent p{
			font-size:14px !important;
			line-height:150% !important;
		}

}	@media only screen and (max-width: 480px){
		#templateHeader .mcnTextContent,#templateHeader .mcnTextContent p{
			font-size:16px !important;
			line-height:150% !important;
		}

}	@media only screen and (max-width: 480px){
		#templateBody .mcnTextContent,#templateBody .mcnTextContent p{
			font-size:16px !important;
			line-height:150% !important;
		}

}	@media only screen and (max-width: 480px){
		#templateUpperColumns .columnContainer .mcnTextContent,#templateUpperColumns .columnContainer .mcnTextContent p{
			font-size:16px !important;
			line-height:150% !important;
		}

}	@media only screen and (max-width: 480px){
		#templateLowerColumns .columnContainer .mcnTextContent,#templateLowerColumns .columnContainer .mcnTextContent p{
			font-size:16px !important;
			line-height:150% !important;
		}

}	@media only screen and (max-width: 480px){
		#templateFooter .mcnTextContent,#templateFooter .mcnTextContent p{
			font-size:14px !important;
			line-height:150% !important;
		}

}</style>
      <center>
        <table id="bodyTable" style="border-collapse:
          collapse;mso-table-lspace: 0pt;mso-table-rspace:
          0pt;-ms-text-size-adjust: 100%;-webkit-text-size-adjust:
          100%;height: 100%;margin: 0;padding: 0;width:
          100%;background-color: #FFFFFF;" border="0" cellpadding="0"
          cellspacing="0" align="center" height="100%" width="100%">
          <tbody>
            <tr>
              <td id="bodyCell" style="mso-line-height-rule:
                exactly;-ms-text-size-adjust:
                100%;-webkit-text-size-adjust: 100%;height: 100%;margin:
                0;padding: 0;width: 100%;border-top: 0;" align="center"
                valign="top">
                <!-- BEGIN TEMPLATE // -->
                <table style="border-collapse:
                  collapse;mso-table-lspace: 0pt;mso-table-rspace:
                  0pt;-ms-text-size-adjust:
                  100%;-webkit-text-size-adjust: 100%;" border="0"
                  cellpadding="0" cellspacing="0" width="100%">
                  <tbody>
                    <tr>
                      <td id="templatePreheader"
                        style="background:#ffffff none no-repeat
                        center/cover;mso-line-height-rule:
                        exactly;-ms-text-size-adjust:
                        100%;-webkit-text-size-adjust:
                        100%;background-color: #ffffff;background-image:
                        none;background-repeat:
                        no-repeat;background-position:
                        center;background-size: cover;border-top:
                        0;border-bottom: 0;padding-top:
                        9px;padding-bottom: 9px;" align="center"
                        valign="top">
                        <!--[if gte mso 9]>
									<table align="center" border="0" cellspacing="0" cellpadding="0" width="600" style="width:600px;">
									<tr>
									<td align="center" valign="top" width="600" style="width:600px;">
									<![endif]-->
                        <table class="templateContainer"
                          style="border-collapse:
                          collapse;mso-table-lspace:
                          0pt;mso-table-rspace:
                          0pt;-ms-text-size-adjust:
                          100%;-webkit-text-size-adjust: 100%;max-width:
                          600px !important;" border="0" cellpadding="0"
                          cellspacing="0" align="center" width="100%">
                          <tbody>
                            <tr>
                              <td class="preheaderContainer"
                                style="mso-line-height-rule:
                                exactly;-ms-text-size-adjust:
                                100%;-webkit-text-size-adjust: 100%;"
                                valign="top">
                                <table class="mcnTextBlock"
                                  style="min-width:
                                  100%;border-collapse:
                                  collapse;mso-table-lspace:
                                  0pt;mso-table-rspace:
                                  0pt;-ms-text-size-adjust:
                                  100%;-webkit-text-size-adjust: 100%;"
                                  border="0" cellpadding="0"
                                  cellspacing="0" width="100%">
                                  <tbody class="mcnTextBlockOuter">
                                    <tr>
                                      <td class="mcnTextBlockInner"
                                        style="padding-top:
                                        9px;mso-line-height-rule:
                                        exactly;-ms-text-size-adjust:
                                        100%;-webkit-text-size-adjust:
                                        100%;" valign="top">
                                        <!--[if mso]>
				<table align="left" border="0" cellspacing="0" cellpadding="0" width="100%" style="width:100%;">
				<tr>
				<![endif]-->
                                        <!--[if mso]>
				<td valign="top" width="600" style="width:600px;">
				<![endif]-->
                                        <table style="max-width:
                                          100%;min-width:
                                          100%;border-collapse:
                                          collapse;mso-table-lspace:
                                          0pt;mso-table-rspace:
                                          0pt;-ms-text-size-adjust:
                                          100%;-webkit-text-size-adjust:
                                          100%;"
                                          class="mcnTextContentContainer"
                                          border="0" cellpadding="0"
                                          cellspacing="0" align="left"
                                          width="100%">
                                          <tbody>
                                            <tr>
                                              <td class="mcnTextContent"
                                                style="padding-top:
                                                0;padding-right:
                                                18px;padding-bottom:
                                                9px;padding-left:
                                                18px;mso-line-height-rule:
exactly;-ms-text-size-adjust: 100%;-webkit-text-size-adjust:
                                                100%;word-break:
                                                break-word;color:
                                                #656565;font-family:
                                                Helvetica;font-size:
                                                12px;line-height:
                                                150%;text-align: left;"
                                                valign="top">
                                                <div style="text-align:
                                                  left;"><a
                                                    moz-do-not-send="true"
href="https://www.bink.com" target="_blank" style="mso-line-height-rule:
exactly;-ms-text-size-adjust: 100%;-webkit-text-size-adjust: 100%;color:
                                                    #656565;font-weight:
normal;text-decoration: underline;"><img moz-do-not-send="true"
src="https://gallery.mailchimp.com/f521b63b94055dfac0d9cda24/images/0de1fdbd-2ebb-444f-a3fe-8e3ef99174a6.png"
                                                      style="width:
                                                      100px;height:
                                                      51px;margin:
                                                      0px;float:
                                                      left;border:
                                                      0;outline:
                                                      none;text-decoration:
none;-ms-interpolation-mode: bicubic;" align="none" height="51"
                                                      width="100"></a></div>
                                                <div style="text-align:
                                                  right;"><br>
                                                  <a
                                                    moz-do-not-send="true"
href="https://www.linkedin.com/company/bink" target="_blank"
                                                    style="mso-line-height-rule:
exactly;-ms-text-size-adjust: 100%;-webkit-text-size-adjust: 100%;color:
                                                    #656565;font-weight:
normal;text-decoration: underline;"><img moz-do-not-send="true"
                                                      alt="LinkedIn"
src="https://gallery.mailchimp.com/f521b63b94055dfac0d9cda24/images/cdb9ab4e-2559-4e42-978f-3367d5e2105d.png"
                                                      style="border:
                                                      0px;width:
                                                      30px;height:
                                                      30px;margin:
                                                      0px;outline:
                                                      none;text-decoration:
none;-ms-interpolation-mode: bicubic;" align="none" height="30"
                                                      width="30"></a>  <a
moz-do-not-send="true" href="https://www.facebook.com/hellobink"
                                                    target="_blank"
                                                    style="mso-line-height-rule:
exactly;-ms-text-size-adjust: 100%;-webkit-text-size-adjust: 100%;color:
                                                    #656565;font-weight:
normal;text-decoration: underline;"><img moz-do-not-send="true"
                                                      alt="Facebook"
src="https://gallery.mailchimp.com/f521b63b94055dfac0d9cda24/images/7183c775-877c-46f9-9ed2-86d2b89c0e71.png"
                                                      style="border:
                                                      0px;width:
                                                      30px;height:
                                                      30px;margin:
                                                      0px;outline:
                                                      none;text-decoration:
none;-ms-interpolation-mode: bicubic;" align="none" height="30"
                                                      width="30"></a>  <a
moz-do-not-send="true" href="http://www.twitter.com/hellobink"
                                                    target="_blank"
                                                    style="mso-line-height-rule:
exactly;-ms-text-size-adjust: 100%;-webkit-text-size-adjust: 100%;color:
                                                    #656565;font-weight:
normal;text-decoration: underline;"><img moz-do-not-send="true"
                                                      alt="Twitter"
src="https://gallery.mailchimp.com/f521b63b94055dfac0d9cda24/images/804d0848-63b0-4f52-b990-e3a0bc379d45.png"
                                                      style="border:
                                                      0px;width:
                                                      36px;height:
                                                      30px;margin:
                                                      0px;outline:
                                                      none;text-decoration:
none;-ms-interpolation-mode: bicubic;" align="none" height="30"
                                                      width="36"></a>   <a
moz-do-not-send="true" href="http://www.instagram.com/binkhq/"
                                                    target="_blank"
                                                    style="mso-line-height-rule:
exactly;-ms-text-size-adjust: 100%;-webkit-text-size-adjust: 100%;color:
                                                    #656565;font-weight:
normal;text-decoration: underline;"><img moz-do-not-send="true"
                                                      alt="Instagram"
src="https://gallery.mailchimp.com/f521b63b94055dfac0d9cda24/images/d30083ab-536e-478a-b140-54475810a8e6.png"
                                                      style="border:
                                                      0px;width:
                                                      30px;height:
                                                      30px;margin:
                                                      0px;outline:
                                                      none;text-decoration:
none;-ms-interpolation-mode: bicubic;" align="none" height="30"
                                                      width="30"></a>  </div>
                                              </td>
                                            </tr>
                                          </tbody>
                                        </table>
                                        <!--[if mso]>
				</td>
				<![endif]-->
                                        <!--[if mso]>
				</tr>
				</table>
				<![endif]--> </td>
                                    </tr>
                                  </tbody>
                                </table>
                              </td>
                            </tr>
                          </tbody>
                        </table>
                        <!--[if gte mso 9]>
									</td>
									</tr>
									</table>
									<![endif]--> </td>
                    </tr>
                    <tr>
                      <td id="templateHeader" style="background:#ffffff
                        none no-repeat
                        center/cover;mso-line-height-rule:
                        exactly;-ms-text-size-adjust:
                        100%;-webkit-text-size-adjust:
                        100%;background-color: #ffffff;background-image:
                        none;background-repeat:
                        no-repeat;background-position:
                        center;background-size: cover;border-top: 4px
                        solid #f20060;border-bottom: 0;padding-top:
                        0px;padding-bottom: 0px;" align="center"
                        valign="top">
                        <!--[if gte mso 9]>
									<table align="center" border="0" cellspacing="0" cellpadding="0" width="600" style="width:600px;">
									<tr>
									<td align="center" valign="top" width="600" style="width:600px;">
									<![endif]-->
                        <table class="templateContainer"
                          style="border-collapse:
                          collapse;mso-table-lspace:
                          0pt;mso-table-rspace:
                          0pt;-ms-text-size-adjust:
                          100%;-webkit-text-size-adjust: 100%;max-width:
                          600px !important;" border="0" cellpadding="0"
                          cellspacing="0" align="center" width="100%">
                          <tbody>
                            <tr>
                              <td class="headerContainer"
                                style="mso-line-height-rule:
                                exactly;-ms-text-size-adjust:
                                100%;-webkit-text-size-adjust: 100%;"
                                valign="top"><br>
                              </td>
                            </tr>
                          </tbody>
                        </table>
                        <!--[if gte mso 9]>
									</td>
									</tr>
									</table>
									<![endif]--> </td>
                    </tr>
                    <tr>
                      <td id="templateBody" style="background:#ffffff
                        none no-repeat
                        center/cover;mso-line-height-rule:
                        exactly;-ms-text-size-adjust:
                        100%;-webkit-text-size-adjust:
                        100%;background-color: #ffffff;background-image:
                        none;background-repeat:
                        no-repeat;background-position:
                        center;background-size: cover;border-top:
                        0;border-bottom: 0;padding-top:
                        0px;padding-bottom: 0;" align="center"
                        valign="top">
                        <!--[if gte mso 9]>
									<table align="center" border="0" cellspacing="0" cellpadding="0" width="600" style="width:600px;">
									<tr>
									<td align="center" valign="top" width="600" style="width:600px;">
									<![endif]-->
                        <table class="templateContainer"
                          style="border-collapse:
                          collapse;mso-table-lspace:
                          0pt;mso-table-rspace:
                          0pt;-ms-text-size-adjust:
                          100%;-webkit-text-size-adjust: 100%;max-width:
                          600px !important;" border="0" cellpadding="0"
                          cellspacing="0" align="center" width="100%">
                          <tbody>
                            <tr>
                              <td class="bodyContainer"
                                style="mso-line-height-rule:
                                exactly;-ms-text-size-adjust:
                                100%;-webkit-text-size-adjust: 100%;"
                                valign="top">
                                <table class="mcnBoxedTextBlock"
                                  style="min-width:
                                  100%;border-collapse:
                                  collapse;mso-table-lspace:
                                  0pt;mso-table-rspace:
                                  0pt;-ms-text-size-adjust:
                                  100%;-webkit-text-size-adjust: 100%;"
                                  border="0" cellpadding="0"
                                  cellspacing="0" width="100%">
                                  <!--[if gte mso 9]>
	<table align="center" border="0" cellspacing="0" cellpadding="0" width="100%">
	<![endif]--> <tbody class="mcnBoxedTextBlockOuter">
                                    <tr>
                                      <td class="mcnBoxedTextBlockInner"
                                        style="mso-line-height-rule:
                                        exactly;-ms-text-size-adjust:
                                        100%;-webkit-text-size-adjust:
                                        100%;" valign="top">
                                        <!--[if gte mso 9]>
				<td align="center" valign="top" ">
				<![endif]-->
                                        <table style="min-width:
                                          100%;border-collapse:
                                          collapse;mso-table-lspace:
                                          0pt;mso-table-rspace:
                                          0pt;-ms-text-size-adjust:
                                          100%;-webkit-text-size-adjust:
                                          100%;"
                                          class="mcnBoxedTextContentContainer"
                                          border="0" cellpadding="0"
                                          cellspacing="0" align="left"
                                          width="100%">
                                          <tbody>
                                            <tr>
                                              <td style="padding-top:
                                                9px;padding-left:
                                                18px;padding-bottom:
                                                9px;padding-right:
                                                18px;mso-line-height-rule:
exactly;-ms-text-size-adjust: 100%;-webkit-text-size-adjust: 100%;">
                                                <table
                                                  class="mcnTextContentContainer"
                                                  style="min-width: 100%
!important;background-color: #FFFFFF;border-collapse:
                                                  collapse;mso-table-lspace:
                                                  0pt;mso-table-rspace:
0pt;-ms-text-size-adjust: 100%;-webkit-text-size-adjust: 100%;"
                                                  border="0"
                                                  cellpadding="18"
                                                  cellspacing="0"
                                                  width="100%">
                                                  <tbody>
                                                    <tr>
                                                      <td
                                                        class="mcnTextContent"
                                                        style="color:
                                                        #666666;font-family:
                                                        Arial,
                                                        'Helvetica
                                                        Neue',
                                                        Helvetica,
                                                        sans-serif;font-size:
                                                        12px;font-style:
normal;font-weight: normal;line-height: 150%;text-align:
                                                        left;mso-line-height-rule:
exactly;-ms-text-size-adjust: 100%;-webkit-text-size-adjust:
                                                        100%;word-break:
                                                        break-word;"
                                                        valign="top">
                                                        <div
                                                          style="text-align:
                                                          center;"><img
moz-do-not-send="true"
src="https://gallery.mailchimp.com/f521b63b94055dfac0d9cda24/images/31e0416b-cd91-4bc6-82ea-387b8a207b35.png"
                                                          style="width:
                                                          98px;height:
                                                          150px;margin:
                                                          0px;border:
                                                          0;outline:
                                                          none;text-decoration:
none;-ms-interpolation-mode: bicubic;" align="none" height="150"
                                                          width="98"></div>
                                                      </td>
                                                    </tr>
                                                  </tbody>
                                                </table>
                                              </td>
                                            </tr>
                                          </tbody>
                                        </table>
                                        <!--[if gte mso 9]>
				</td>
				<![endif]-->
                                        <!--[if gte mso 9]>
                </tr>
                </table>
				<![endif]--> </td>
                                    </tr>
                                  </tbody>
                                </table>
                                <table class="mcnButtonBlock"
                                  style="min-width:
                                  100%;border-collapse:
                                  collapse;mso-table-lspace:
                                  0pt;mso-table-rspace:
                                  0pt;-ms-text-size-adjust:
                                  100%;-webkit-text-size-adjust: 100%;"
                                  border="0" cellpadding="0"
                                  cellspacing="0" width="100%">
                                  <tbody class="mcnButtonBlockOuter">
                                    <tr>
                                      <td style="padding-top:
                                        0;padding-right:
                                        18px;padding-bottom:
                                        18px;padding-left:
                                        18px;mso-line-height-rule:
                                        exactly;-ms-text-size-adjust:
                                        100%;-webkit-text-size-adjust:
                                        100%;"
                                        class="mcnButtonBlockInner"
                                        align="center" valign="top">
                                        <table
                                          class="mcnButtonContentContainer"
                                          style="border-collapse:
                                          separate
                                          !important;border-top-left-radius:
                                          3px;border-top-right-radius:
                                          3px;border-bottom-right-radius:
                                          3px;border-bottom-left-radius:
                                          3px;background-color:
                                          #F20060;mso-table-lspace:
                                          0pt;mso-table-rspace:
                                          0pt;-ms-text-size-adjust:
                                          100%;-webkit-text-size-adjust:
                                          100%;" border="0"
                                          cellpadding="0"
                                          cellspacing="0">
                                          <tbody>
                                            <tr>
                                              <td
                                                class="mcnButtonContent"
                                                style="font-family:
                                                'Helvetica Neue',
                                                Helvetica, Arial,
                                                Verdana,
                                                sans-serif;font-size:
                                                16px;padding:
                                                15px;mso-line-height-rule:
exactly;-ms-text-size-adjust: 100%;-webkit-text-size-adjust: 100%;"
                                                align="center"
                                                valign="middle"> <a
                                                  moz-do-not-send="true"
                                                  class="mcnButton "
                                                  title="Get a new
                                                  password"
                                                  href="{{ link }}"
                                                  target="_blank"
                                                  style="font-weight:
                                                  bold;letter-spacing:
                                                  normal;line-height:
                                                  100%;text-align:
                                                  center;text-decoration:
                                                  none;color:
                                                  #FFFFFF;mso-line-height-rule:
exactly;-ms-text-size-adjust: 100%;-webkit-text-size-adjust:
                                                  100%;display: block;">Get
                                                  a new password</a> </td>
                                            </tr>
                                          </tbody>
                                        </table>
                                      </td>
                                    </tr>
                                  </tbody>
                                </table>
                                <table class="mcnBoxedTextBlock"
                                  style="min-width:
                                  100%;border-collapse:
                                  collapse;mso-table-lspace:
                                  0pt;mso-table-rspace:
                                  0pt;-ms-text-size-adjust:
                                  100%;-webkit-text-size-adjust: 100%;"
                                  border="0" cellpadding="0"
                                  cellspacing="0" width="100%">
                                  <!--[if gte mso 9]>
	<table align="center" border="0" cellspacing="0" cellpadding="0" width="100%">
	<![endif]--> <tbody class="mcnBoxedTextBlockOuter">
                                    <tr>
                                      <td class="mcnBoxedTextBlockInner"
                                        style="mso-line-height-rule:
                                        exactly;-ms-text-size-adjust:
                                        100%;-webkit-text-size-adjust:
                                        100%;" valign="top">
                                        <!--[if gte mso 9]>
				<td align="center" valign="top" ">
				<![endif]-->
                                        <table style="min-width:
                                          100%;border-collapse:
                                          collapse;mso-table-lspace:
                                          0pt;mso-table-rspace:
                                          0pt;-ms-text-size-adjust:
                                          100%;-webkit-text-size-adjust:
                                          100%;"
                                          class="mcnBoxedTextContentContainer"
                                          border="0" cellpadding="0"
                                          cellspacing="0" align="left"
                                          width="100%">
                                          <tbody>
                                            <tr>
                                              <td style="padding-top:
                                                9px;padding-left:
                                                18px;padding-bottom:
                                                9px;padding-right:
                                                18px;mso-line-height-rule:
exactly;-ms-text-size-adjust: 100%;-webkit-text-size-adjust: 100%;">
                                                <table
                                                  class="mcnTextContentContainer"
                                                  style="min-width: 100%
!important;background-color: #FFFFFF;border-collapse:
                                                  collapse;mso-table-lspace:
                                                  0pt;mso-table-rspace:
0pt;-ms-text-size-adjust: 100%;-webkit-text-size-adjust: 100%;"
                                                  border="0"
                                                  cellpadding="18"
                                                  cellspacing="0"
                                                  width="100%">
                                                  <tbody>
                                                    <tr>
                                                      <td
                                                        class="mcnTextContent"
                                                        style="color:
                                                        #666666;font-family:
                                                        Arial,
                                                        'Helvetica
                                                        Neue',
                                                        Helvetica,
                                                        sans-serif;font-size:
                                                        12px;font-style:
normal;font-weight: normal;line-height: 150%;text-align:
                                                        left;mso-line-height-rule:
exactly;-ms-text-size-adjust: 100%;-webkit-text-size-adjust:
                                                        100%;word-break:
                                                        break-word;"
                                                        valign="top">
                                                        <div
                                                          style="text-align:
                                                          justify;"><font
face="arial, sans-serif">Effortlessly reset your Bink App password by selecting “Get a new password”</div>
                                                        <div
                                                          style="text-align:
                                                          justify;"> </div>
                                                        <div
                                                          style="text-align:
                                                          justify;"><font
face="arial, sans-serif"><br>If you didn’t request a password reset, please get in touch with us immediately at </font><a
moz-do-not-send="true"
href="mailto:support@bink.com?subject=Urgent%3A%20Password%20Reset%20Not%20Requested"
target="_blank" style="mso-line-height-rule:
                                                          exactly;-ms-text-size-adjust:
100%;-webkit-text-size-adjust: 100%;color: #00b9ff;font-weight:
                                                          normal;text-decoration:
                                                          underline;">support@bink.com</a>.</div>
                                                      </td>
                                                    </tr>
                                                  </tbody>
                                                </table>
                                              </td>
                                            </tr>
                                          </tbody>
                                        </table>
                                        <!--[if gte mso 9]>
				</td>
				<![endif]-->
                                        <!--[if gte mso 9]>
                </tr>
                </table>
				<![endif]--> </td>
                                    </tr>
                                  </tbody>
                                </table>
                              </td>
                            </tr>
                          </tbody>
                        </table>
                        <!--[if gte mso 9]>
									</td>
									</tr>
									</table>
									<![endif]--> </td>
                    </tr>
                    <tr>
                      <td id="templateUpperColumns"
                        style="background:#ffffff none no-repeat
                        center/cover;mso-line-height-rule:
                        exactly;-ms-text-size-adjust:
                        100%;-webkit-text-size-adjust:
                        100%;background-color: #ffffff;background-image:
                        none;background-repeat:
                        no-repeat;background-position:
                        center;background-size: cover;border-top:
                        0;border-bottom: 0;padding-top:
                        0;padding-bottom: 0px;" align="center"
                        valign="top">
                        <table class="templateContainer"
                          style="border-collapse:
                          collapse;mso-table-lspace:
                          0pt;mso-table-rspace:
                          0pt;-ms-text-size-adjust:
                          100%;-webkit-text-size-adjust: 100%;max-width:
                          600px !important;" border="0" cellpadding="0"
                          cellspacing="0" width="100%">
                          <tbody>
                            <tr>
                              <td style="mso-line-height-rule:
                                exactly;-ms-text-size-adjust:
                                100%;-webkit-text-size-adjust: 100%;"
                                valign="top">
                                <!--[if gte mso 9]>
												<table align="center" border="0" cellspacing="0" cellpadding="0" width="600" style="width:600px;">
												<tr>
												<td align="center" valign="top" width="200" style="width:200px;">
												<![endif]-->
                                <table class="columnWrapper"
                                  style="border-collapse:
                                  collapse;mso-table-lspace:
                                  0pt;mso-table-rspace:
                                  0pt;-ms-text-size-adjust:
                                  100%;-webkit-text-size-adjust: 100%;"
                                  border="0" cellpadding="0"
                                  cellspacing="0" align="left"
                                  width="200">
                                  <tbody>
                                    <tr>
                                      <td class="columnContainer"
                                        style="mso-line-height-rule:
                                        exactly;-ms-text-size-adjust:
                                        100%;-webkit-text-size-adjust:
                                        100%;" valign="top"><br>
                                      </td>
                                    </tr>
                                  </tbody>
                                </table>
                                <!--[if gte mso 9]>
												</td>
												<td align="center" valign="top" width="200" style="width:200px;">
												<![endif]-->
                                <table class="columnWrapper"
                                  style="border-collapse:
                                  collapse;mso-table-lspace:
                                  0pt;mso-table-rspace:
                                  0pt;-ms-text-size-adjust:
                                  100%;-webkit-text-size-adjust: 100%;"
                                  border="0" cellpadding="0"
                                  cellspacing="0" align="left"
                                  width="200">
                                  <tbody>
                                    <tr>
                                      <td class="columnContainer"
                                        style="mso-line-height-rule:
                                        exactly;-ms-text-size-adjust:
                                        100%;-webkit-text-size-adjust:
                                        100%;" valign="top"><br>
                                      </td>
                                    </tr>
                                  </tbody>
                                </table>
                                <!--[if gte mso 9]>
												</td>
												<td align="center" valign="top" width="200" style="width:200px;">
												<![endif]-->
                                <table class="columnWrapper"
                                  style="border-collapse:
                                  collapse;mso-table-lspace:
                                  0pt;mso-table-rspace:
                                  0pt;-ms-text-size-adjust:
                                  100%;-webkit-text-size-adjust: 100%;"
                                  border="0" cellpadding="0"
                                  cellspacing="0" align="left"
                                  width="200">
                                  <tbody>
                                    <tr>
                                      <td class="columnContainer"
                                        style="mso-line-height-rule:
                                        exactly;-ms-text-size-adjust:
                                        100%;-webkit-text-size-adjust:
                                        100%;" valign="top"><br>
                                      </td>
                                    </tr>
                                  </tbody>
                                </table>
                                <!--[if gte mso 9]>
												</td>
												</tr>
												</table>
												<![endif]--> </td>
                            </tr>
                          </tbody>
                        </table>
                      </td>
                    </tr>
                    <tr>
                      <td id="templateLowerColumns"
                        style="background:#ffffff none no-repeat
                        center/cover;mso-line-height-rule:
                        exactly;-ms-text-size-adjust:
                        100%;-webkit-text-size-adjust:
                        100%;background-color: #ffffff;background-image:
                        none;background-repeat:
                        no-repeat;background-position:
                        center;background-size: cover;border-top:
                        0;border-bottom: 1px none;padding-top:
                        2px;padding-bottom: 2px;" align="center"
                        valign="top">
                        <table class="templateContainer"
                          style="border-collapse:
                          collapse;mso-table-lspace:
                          0pt;mso-table-rspace:
                          0pt;-ms-text-size-adjust:
                          100%;-webkit-text-size-adjust: 100%;max-width:
                          600px !important;" border="0" cellpadding="0"
                          cellspacing="0" width="100%">
                          <tbody>
                            <tr>
                              <td style="mso-line-height-rule:
                                exactly;-ms-text-size-adjust:
                                100%;-webkit-text-size-adjust: 100%;"
                                valign="top">
                                <!--[if gte mso 9]>
												<table align="center" border="0" cellspacing="0" cellpadding="0" width="600" style="width:600px;">
												<tr>
												<td align="center" valign="top" width="300" style="width:300px;">
												<![endif]-->
                                <table class="columnWrapper"
                                  style="border-collapse:
                                  collapse;mso-table-lspace:
                                  0pt;mso-table-rspace:
                                  0pt;-ms-text-size-adjust:
                                  100%;-webkit-text-size-adjust: 100%;"
                                  border="0" cellpadding="0"
                                  cellspacing="0" align="left"
                                  width="300">
                                  <tbody>
                                    <tr>
                                      <td class="columnContainer"
                                        style="mso-line-height-rule:
                                        exactly;-ms-text-size-adjust:
                                        100%;-webkit-text-size-adjust:
                                        100%;" valign="top"><br>
                                      </td>
                                    </tr>
                                  </tbody>
                                </table>
                                <!--[if gte mso 9]>
												</td>
												<td align="center" valign="top" width="300" style="width:300px;">
												<![endif]-->
                                <table class="columnWrapper"
                                  style="border-collapse:
                                  collapse;mso-table-lspace:
                                  0pt;mso-table-rspace:
                                  0pt;-ms-text-size-adjust:
                                  100%;-webkit-text-size-adjust: 100%;"
                                  border="0" cellpadding="0"
                                  cellspacing="0" align="left"
                                  width="300">
                                  <tbody>
                                    <tr>
                                      <td class="columnContainer"
                                        style="mso-line-height-rule:
                                        exactly;-ms-text-size-adjust:
                                        100%;-webkit-text-size-adjust:
                                        100%;" valign="top"><br>
                                      </td>
                                    </tr>
                                  </tbody>
                                </table>
                                <!--[if gte mso 9]>
												</td>
												</tr>
												</table>
												<![endif]--> </td>
                            </tr>
                          </tbody>
                        </table>
                      </td>
                    </tr>
                    <tr>
                      <td id="templateFooter" style="background:#ffffff
                        none no-repeat
                        center/cover;mso-line-height-rule:
                        exactly;-ms-text-size-adjust:
                        100%;-webkit-text-size-adjust:
                        100%;background-color: #ffffff;background-image:
                        none;background-repeat:
                        no-repeat;background-position:
                        center;background-size: cover;border-top:
                        0;border-bottom: 0;padding-top:
                        1px;padding-bottom: 1px;" align="center"
                        valign="top">
                        <!--[if gte mso 9]>
									<table align="center" border="0" cellspacing="0" cellpadding="0" width="600" style="width:600px;">
									<tr>
									<td align="center" valign="top" width="600" style="width:600px;">
									<![endif]-->
                        <table class="templateContainer"
                          style="border-collapse:
                          collapse;mso-table-lspace:
                          0pt;mso-table-rspace:
                          0pt;-ms-text-size-adjust:
                          100%;-webkit-text-size-adjust: 100%;max-width:
                          600px !important;" border="0" cellpadding="0"
                          cellspacing="0" align="center" width="100%">
                          <tbody>
                            <tr>
                              <td class="footerContainer"
                                style="mso-line-height-rule:
                                exactly;-ms-text-size-adjust:
                                100%;-webkit-text-size-adjust: 100%;"
                                valign="top">
                                <table class="mcnDividerBlock"
                                  style="min-width:
                                  100%;border-collapse:
                                  collapse;mso-table-lspace:
                                  0pt;mso-table-rspace:
                                  0pt;-ms-text-size-adjust:
                                  100%;-webkit-text-size-adjust:
                                  100%;table-layout: fixed !important;"
                                  border="0" cellpadding="0"
                                  cellspacing="0" width="100%">
                                  <tbody class="mcnDividerBlockOuter">
                                    <tr>
                                      <td class="mcnDividerBlockInner"
                                        style="min-width: 100%;padding:
                                        0px 18px;mso-line-height-rule:
                                        exactly;-ms-text-size-adjust:
                                        100%;-webkit-text-size-adjust:
                                        100%;">
                                        <table class="mcnDividerContent"
                                          style="min-width:
                                          100%;border-top-width:
                                          2px;border-top-style:
                                          solid;border-top-color:
                                          #EAEAEA;border-collapse:
                                          collapse;mso-table-lspace:
                                          0pt;mso-table-rspace:
                                          0pt;-ms-text-size-adjust:
                                          100%;-webkit-text-size-adjust:
                                          100%;" border="0"
                                          cellpadding="0"
                                          cellspacing="0" width="100%">
                                          <tbody>
                                            <tr>
                                              <td
                                                style="mso-line-height-rule:
exactly;-ms-text-size-adjust: 100%;-webkit-text-size-adjust: 100%;"> <span></span>
                                                <br>
                                              </td>
                                            </tr>
                                          </tbody>
                                        </table>
                                        <!--
                <td class="mcnDividerBlockInner" style="padding: 18px;">
                <hr class="mcnDividerContent" style="border-bottom-color:none; border-left-color:none; border-right-color:none; border-bottom-width:0; border-left-width:0; border-right-width:0; margin-top:0; margin-right:0; margin-bottom:0; margin-left:0;" />
--> </td>
                                    </tr>
                                  </tbody>
                                </table>
                                <table class="mcnTextBlock"
                                  style="min-width:
                                  100%;border-collapse:
                                  collapse;mso-table-lspace:
                                  0pt;mso-table-rspace:
                                  0pt;-ms-text-size-adjust:
                                  100%;-webkit-text-size-adjust: 100%;"
                                  border="0" cellpadding="0"
                                  cellspacing="0" width="100%">
                                  <tbody class="mcnTextBlockOuter">
                                    <tr>
                                      <td class="mcnTextBlockInner"
                                        style="padding-top:
                                        9px;mso-line-height-rule:
                                        exactly;-ms-text-size-adjust:
                                        100%;-webkit-text-size-adjust:
                                        100%;" valign="top">
                                        <!--[if mso]>
				<table align="left" border="0" cellspacing="0" cellpadding="0" width="100%" style="width:100%;">
				<tr>
				<![endif]-->
                                        <!--[if mso]>
				<td valign="top" width="600" style="width:600px;">
				<![endif]-->
                                        <table style="max-width:
                                          100%;min-width:
                                          100%;border-collapse:
                                          collapse;mso-table-lspace:
                                          0pt;mso-table-rspace:
                                          0pt;-ms-text-size-adjust:
                                          100%;-webkit-text-size-adjust:
                                          100%;"
                                          class="mcnTextContentContainer"
                                          border="0" cellpadding="0"
                                          cellspacing="0" align="left"
                                          width="100%">
                                          <tbody>
                                            <tr>
                                              <td class="mcnTextContent"
                                                style="padding-top:
                                                0;padding-right:
                                                18px;padding-bottom:
                                                9px;padding-left:
                                                18px;mso-line-height-rule:
exactly;-ms-text-size-adjust: 100%;-webkit-text-size-adjust:
                                                100%;word-break:
                                                break-word;color:
                                                #656565;font-family:
                                                Helvetica;font-size:
                                                12px;line-height:
                                                150%;text-align: left;"
                                                valign="top">
                                                <div style="text-align:
                                                  center;"><em>Copyright
                                                    © 2020 Bink, All
                                                    rights reserved.</em><br>
                                                  <br>
                                                  <strong>Our mailing
                                                    address is:</strong><br>
                                                  Second Floor, 2 Queens
Square, Lyndhurst Road, Ascot, Berkshire, SL5 9FE</div>
                                              </td>
                                            </tr>
                                          </tbody>
                                        </table>
                                        <!--[if mso]>
				</td>
				<![endif]-->
                                        <!--[if mso]>
				</tr>
				</table>
				<![endif]--> </td>
                                    </tr>
                                  </tbody>
                                </table>
                              </td>
                            </tr>
                          </tbody>
                        </table>
                        <!--[if gte mso 9]>
									</td>
									</tr>
									</table>
									<![endif]--> </td>
                    </tr>
                  </tbody>
                </table>
                <!-- // END TEMPLATE --> </td>
            </tr>
          </tbody>
        </table>
      </center>
    </div>
  </body>
{% endblock %}
