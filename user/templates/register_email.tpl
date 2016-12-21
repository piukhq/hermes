{% extends "mail_templated/base.tpl" %}

{% block subject %}
Getting Started with Bink!! 🚀
{% endblock %}

{% block html %}
<head>
<meta http-equiv="Content-Type" content="text/html; charset=utf-8">
  </head>
  <body bgcolor="#FFFFFF" text="#000000">
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
		#bodyCell{
			padding:10px;
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
			background-color:#ffffff;
		}
		#bodyCell{
			border-top:0;
		}
		.templateContainer{
			border:0;
		}
		h1{
			color:#202020;
			font-family:Helvetica;
			font-size:26px;
			font-style:normal;
			font-weight:bold;
			line-height:125%;
			letter-spacing:normal;
			text-align:left;
		}
		h2{
			color:#202020;
			font-family:Helvetica;
			font-size:22px;
			font-style:normal;
			font-weight:bold;
			line-height:125%;
			letter-spacing:normal;
			text-align:left;
		}
		h3{
			color:#202020;
			font-family:Helvetica;
			font-size:20px;
			font-style:normal;
			font-weight:bold;
			line-height:125%;
			letter-spacing:normal;
			text-align:left;
		}
		h4{
			color:#202020;
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
			padding-top:0px;
			padding-bottom:0px;
		}
		#templatePreheader .mcnTextContent,#templatePreheader .mcnTextContent p{
			color:#8b8d8e;
			font-family:Helvetica;
			font-size:12px;
			line-height:150%;
			text-align:left;
		}
		#templatePreheader .mcnTextContent a,#templatePreheader .mcnTextContent p a{
			color:#8b8d8e;
			font-weight:normal;
			text-decoration:underline;
		}
		#templateHeader{
			background-color:#ffffff;
			background-image:none;
			background-repeat:no-repeat;
			background-position:center;
			background-size:cover;
			border-top:0;
			border-bottom:0;
			padding-top:0px;
			padding-bottom:0px;
		}
		#templateHeader .mcnTextContent,#templateHeader .mcnTextContent p{
			color:#202020;
			font-family:Helvetica;
			font-size:16px;
			line-height:150%;
			text-align:left;
		}
		#templateHeader .mcnTextContent a,#templateHeader .mcnTextContent p a{
			color:#2BAADF;
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
			border-bottom:2px solid #eaeaea;
			padding-top:10px;
			padding-bottom:10px;
		}
		#templateUpperColumns .columnContainer .mcnTextContent,#templateUpperColumns .columnContainer .mcnTextContent p{
			color:#202020;
			font-family:Helvetica;
			font-size:16px;
			line-height:150%;
			text-align:left;
		}
		#templateUpperColumns .columnContainer .mcnTextContent a,#templateUpperColumns .columnContainer .mcnTextContent p a{
			color:#2BAADF;
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
			padding-bottom:0px;
		}
		#templateBody .mcnTextContent,#templateBody .mcnTextContent p{
			color:#202020;
			font-family:Helvetica;
			font-size:16px;
			line-height:150%;
			text-align:left;
		}
		#templateBody .mcnTextContent a,#templateBody .mcnTextContent p a{
			color:#2BAADF;
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
			border-bottom:2px solid #EAEAEA;
			padding-top:10px;
			padding-bottom:10px;
		}
		#templateLowerColumns .columnContainer .mcnTextContent,#templateLowerColumns .columnContainer .mcnTextContent p{
			color:#202020;
			font-family:Helvetica;
			font-size:16px;
			line-height:150%;
			text-align:left;
		}
		#templateLowerColumns .columnContainer .mcnTextContent a,#templateLowerColumns .columnContainer .mcnTextContent p a{
			color:#2BAADF;
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
			padding-top:0px;
			padding-bottom:0px;
		}
		#templateFooter .mcnTextContent,#templateFooter .mcnTextContent p{
			color:#656565;
			font-family:Helvetica;
			font-size:12px;
			line-height:150%;
			text-align:center;
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
		#templateUpperColumns .columnContainer .mcnTextContent,#templateUpperColumns .columnContainer .mcnTextContent p{
			font-size:16px !important;
			line-height:150% !important;
		}

}	@media only screen and (max-width: 480px){
		#templateBody .mcnTextContent,#templateBody .mcnTextContent p{
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
          100%;background-color: #ffffff;" border="0" cellpadding="0" cellspacing="0" align="center" height="100%" width="100%">
          <tbody>
            <tr>
              <td id="bodyCell" style="mso-line-height-rule:
                exactly;-ms-text-size-adjust:
                100%;-webkit-text-size-adjust: 100%;height: 100%;margin:
                0;padding: 10px;width: 100%;border-top: 0;" align="center" valign="top">
                <!-- BEGIN TEMPLATE // -->
                <!--[if gte mso 9]>
						<table align="center" border="0" cellspacing="0" cellpadding="0" width="600" style="width:600px;">
						<tr>
						<td align="center" valign="top" width="600" style="width:600px;">
						<![endif]-->
                <table class="templateContainer" style="border-collapse:
                  collapse;mso-table-lspace: 0pt;mso-table-rspace:
                  0pt;-ms-text-size-adjust:
                  100%;-webkit-text-size-adjust: 100%;border:
                  0;max-width: 600px !important;" border="0" cellpadding="0" cellspacing="0" width="100%">
                  <tbody>
                    <tr>
                      <td id="templatePreheader" style="background:#ffffff none no-repeat
                        center/cover;mso-line-height-rule:
                        exactly;-ms-text-size-adjust:
                        100%;-webkit-text-size-adjust:
                        100%;background-color: #ffffff;background-image:
                        none;background-repeat:
                        no-repeat;background-position:
                        center;background-size: cover;border-top:
                        0;border-bottom: 0;padding-top:
                        0px;padding-bottom: 0px;" valign="top">
                        <table class="mcnTextBlock" style="min-width:
                          100%;border-collapse:
                          collapse;mso-table-lspace:
                          0pt;mso-table-rspace:
                          0pt;-ms-text-size-adjust:
                          100%;-webkit-text-size-adjust: 100%;" border="0" cellpadding="0" cellspacing="0" width="100%">
                          <tbody class="mcnTextBlockOuter">
                            <tr>
                              <td class="mcnTextBlockInner" style="padding-top:
                                9px;mso-line-height-rule:
                                exactly;-ms-text-size-adjust:
                                100%;-webkit-text-size-adjust: 100%;" valign="top">
                                <!--[if mso]>
				<table align="left" border="0" cellspacing="0" cellpadding="0" width="100%" style="width:100%;">
				<tr>
				<![endif]-->
                                <!--[if mso]>
				<td valign="top" width="600" style="width:600px;">
				<![endif]-->
                                <table style="max-width: 100%;min-width:
                                  100%;border-collapse:
                                  collapse;mso-table-lspace:
                                  0pt;mso-table-rspace:
                                  0pt;-ms-text-size-adjust:
                                  100%;-webkit-text-size-adjust: 100%;" class="mcnTextContentContainer" border="0" cellpadding="0" cellspacing="0" align="left" width="100%">
                                  <tbody>
                                    <tr>
                                      <td class="mcnTextContent" style="padding-top:
                                        0;padding-right:
                                        18px;padding-bottom:
                                        9px;padding-left:
                                        18px;mso-line-height-rule:
                                        exactly;-ms-text-size-adjust:
                                        100%;-webkit-text-size-adjust:
                                        100%;word-break:
                                        break-word;color:
                                        #8b8d8e;font-family:
                                        Helvetica;font-size:
                                        12px;line-height:
                                        150%;text-align: left;" valign="top">
                                        <div style="text-align: right;"><a moz-do-not-send="true" href="http://www.bink.com" target="_blank" style="mso-line-height-rule:
exactly;-ms-text-size-adjust: 100%;-webkit-text-size-adjust: 100%;color:
                                            #8b8d8e;font-weight:
                                            normal;text-decoration:
                                            underline;"><img moz-do-not-send="true" src="https://gallery.mailchimp.com/ec044a65c525952557abbcb26/images/f4142aae-f90c-4cfa-8164-9a8a94370382.png" style="float: left;width:
                                              97px;height: 50px;margin:
                                              0px;border: 0;outline:
                                              none;text-decoration:
                                              none;-ms-interpolation-mode:
                                              bicubic;" align="none" height="50" width="97"></a>&nbsp;<br>
                                          <span style="font-family:arial,helvetica
                                            neue,helvetica,sans-serif"><span style="color:#f20060"><strong>Thanks
                                                for&nbsp;joining us!</strong></span></span><br>
                                          &nbsp;</div>
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
                    <tr>
                      <td id="templateHeader" style="background:#ffffff
                        none no-repeat
                        center/cover;mso-line-height-rule:
                        exactly;-ms-text-size-adjust:
                        100%;-webkit-text-size-adjust:
                        100%;background-color: #ffffff;background-image:
                        none;background-repeat:
                        no-repeat;background-position:
                        center;background-size: cover;border-top:
                        0;border-bottom: 0;padding-top:
                        0px;padding-bottom: 0px;" valign="top">
                        <table class="mcnImageBlock" style="min-width:
                          100%;border-collapse:
                          collapse;mso-table-lspace:
                          0pt;mso-table-rspace:
                          0pt;-ms-text-size-adjust:
                          100%;-webkit-text-size-adjust: 100%;" border="0" cellpadding="0" cellspacing="0" width="100%">
                          <tbody class="mcnImageBlockOuter">
                            <tr>
                              <td style="padding:
                                0px;mso-line-height-rule:
                                exactly;-ms-text-size-adjust:
                                100%;-webkit-text-size-adjust: 100%;" class="mcnImageBlockInner" valign="top">
                                <table class="mcnImageContentContainer" style="min-width:
                                  100%;border-collapse:
                                  collapse;mso-table-lspace:
                                  0pt;mso-table-rspace:
                                  0pt;-ms-text-size-adjust:
                                  100%;-webkit-text-size-adjust: 100%;" border="0" cellpadding="0" cellspacing="0" align="left" width="100%">
                                  <tbody>
                                    <tr>
                                      <td class="mcnImageContent" style="padding-right:
                                        0px;padding-left:
                                        0px;padding-top:
                                        0;padding-bottom: 0;text-align:
                                        center;mso-line-height-rule:
                                        exactly;-ms-text-size-adjust:
                                        100%;-webkit-text-size-adjust:
                                        100%;" valign="top"> <img moz-do-not-send="true" alt="" src="https://gallery.mailchimp.com/ec044a65c525952557abbcb26/_compresseds/448517f0-58a8-4ff9-82a1-3b22a7541767.jpg" style="max-width:
                                          1600px;padding-bottom:
                                          0;display: inline
                                          !important;vertical-align:
                                          bottom;border: 0;height:
                                          auto;outline:
                                          none;text-decoration:
                                          none;-ms-interpolation-mode:
                                          bicubic;" class="mcnImage" align="middle" width="600"> </td>
                                    </tr>
                                  </tbody>
                                </table>
                              </td>
                            </tr>
                          </tbody>
                        </table>
                      </td>
                    </tr>
                    <tr>
                      <td id="templateUpperColumns" style="background:#ffffff none no-repeat
                        center/cover;mso-line-height-rule:
                        exactly;-ms-text-size-adjust:
                        100%;-webkit-text-size-adjust:
                        100%;background-color: #ffffff;background-image:
                        none;background-repeat:
                        no-repeat;background-position:
                        center;background-size: cover;border-top:
                        0;border-bottom: 2px solid #eaeaea;padding-top:
                        10px;padding-bottom: 10px;" valign="top">
                        <!--[if gte mso 9]>
									<table align="center" border="0" cellspacing="0" cellpadding="0" width="600" style="width:600px;">
									<tr>
									<td align="center" valign="top" width="200" style="width:200px;">
									<![endif]-->
                        <table class="columnWrapper" style="border-collapse:
                          collapse;mso-table-lspace:
                          0pt;mso-table-rspace:
                          0pt;-ms-text-size-adjust:
                          100%;-webkit-text-size-adjust: 100%;" border="0" cellpadding="0" cellspacing="0" align="left" width="200">
                          <tbody>
                            <tr>
                              <td class="columnContainer" style="mso-line-height-rule:
                                exactly;-ms-text-size-adjust:
                                100%;-webkit-text-size-adjust: 100%;" valign="top">
                                <table class="mcnImageBlock" style="min-width:
                                  100%;border-collapse:
                                  collapse;mso-table-lspace:
                                  0pt;mso-table-rspace:
                                  0pt;-ms-text-size-adjust:
                                  100%;-webkit-text-size-adjust: 100%;" border="0" cellpadding="0" cellspacing="0" width="100%">
                                  <tbody class="mcnImageBlockOuter">
                                    <tr>
                                      <td style="padding:
                                        9px;mso-line-height-rule:
                                        exactly;-ms-text-size-adjust:
                                        100%;-webkit-text-size-adjust:
                                        100%;" class="mcnImageBlockInner" valign="top">
                                        <table class="mcnImageContentContainer" style="min-width:
                                          100%;border-collapse:
                                          collapse;mso-table-lspace:
                                          0pt;mso-table-rspace:
                                          0pt;-ms-text-size-adjust:
                                          100%;-webkit-text-size-adjust:
                                          100%;" border="0" cellpadding="0" cellspacing="0" align="left" width="100%">
                                          <tbody>
                                            <tr>
                                              <td class="mcnImageContent" style="padding-right:
                                                9px;padding-left:
                                                9px;padding-top:
                                                0;padding-bottom:
                                                0;text-align:
                                                center;mso-line-height-rule:
exactly;-ms-text-size-adjust: 100%;-webkit-text-size-adjust: 100%;" valign="top"> <a moz-do-not-send="true" href="http://www.bink.com/how-to-add-loyalty-card" title="" class="" target="_blank" style="mso-line-height-rule:
exactly;-ms-text-size-adjust: 100%;-webkit-text-size-adjust: 100%;"> <img moz-do-not-send="true" alt="" src="https://gallery.mailchimp.com/ec044a65c525952557abbcb26/images/53ddcd72-6b57-456d-8969-f38cdea0ca9b.jpg" style="max-width:
                                                    1800px;padding-bottom:
                                                    0;display: inline
                                                    !important;vertical-align:
                                                    bottom;border:
                                                    0;height:
                                                    auto;outline:
                                                    none;text-decoration:
none;-ms-interpolation-mode: bicubic;" class="mcnImage" align="middle" width="164"> </a> </td>
                                            </tr>
                                          </tbody>
                                        </table>
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
									<td align="center" valign="top" width="200" style="width:200px;">
									<![endif]-->
                        <table class="columnWrapper" style="border-collapse:
                          collapse;mso-table-lspace:
                          0pt;mso-table-rspace:
                          0pt;-ms-text-size-adjust:
                          100%;-webkit-text-size-adjust: 100%;" border="0" cellpadding="0" cellspacing="0" align="left" width="200">
                          <tbody>
                            <tr>
                              <td class="columnContainer" style="mso-line-height-rule:
                                exactly;-ms-text-size-adjust:
                                100%;-webkit-text-size-adjust: 100%;" valign="top">
                                <table class="mcnImageBlock" style="min-width:
                                  100%;border-collapse:
                                  collapse;mso-table-lspace:
                                  0pt;mso-table-rspace:
                                  0pt;-ms-text-size-adjust:
                                  100%;-webkit-text-size-adjust: 100%;" border="0" cellpadding="0" cellspacing="0" width="100%">
                                  <tbody class="mcnImageBlockOuter">
                                    <tr>
                                      <td style="padding:
                                        9px;mso-line-height-rule:
                                        exactly;-ms-text-size-adjust:
                                        100%;-webkit-text-size-adjust:
                                        100%;" class="mcnImageBlockInner" valign="top">
                                        <table class="mcnImageContentContainer" style="min-width:
                                          100%;border-collapse:
                                          collapse;mso-table-lspace:
                                          0pt;mso-table-rspace:
                                          0pt;-ms-text-size-adjust:
                                          100%;-webkit-text-size-adjust:
                                          100%;" border="0" cellpadding="0" cellspacing="0" align="left" width="100%">
                                          <tbody>
                                            <tr>
                                              <td class="mcnImageContent" style="padding-right:
                                                9px;padding-left:
                                                9px;padding-top:
                                                0;padding-bottom:
                                                0;text-align:
                                                center;mso-line-height-rule:
exactly;-ms-text-size-adjust: 100%;-webkit-text-size-adjust: 100%;" valign="top"> <a moz-do-not-send="true" href="http://www.bink.com/how-to-link-loyalty-card" title="" class="" target="_blank" style="mso-line-height-rule:
exactly;-ms-text-size-adjust: 100%;-webkit-text-size-adjust: 100%;"> <img moz-do-not-send="true" alt="" src="https://gallery.mailchimp.com/ec044a65c525952557abbcb26/images/33918eb8-da22-4e0b-bf28-99747f2fbf7b.jpg" style="max-width:
                                                    1800px;padding-bottom:
                                                    0;display: inline
                                                    !important;vertical-align:
                                                    bottom;border:
                                                    0;height:
                                                    auto;outline:
                                                    none;text-decoration:
none;-ms-interpolation-mode: bicubic;" class="mcnImage" align="middle" width="164"> </a> </td>
                                            </tr>
                                          </tbody>
                                        </table>
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
									<td align="center" valign="top" width="200" style="width:200px;">
									<![endif]-->
                        <table class="columnWrapper" style="border-collapse:
                          collapse;mso-table-lspace:
                          0pt;mso-table-rspace:
                          0pt;-ms-text-size-adjust:
                          100%;-webkit-text-size-adjust: 100%;" border="0" cellpadding="0" cellspacing="0" align="left" width="200">
                          <tbody>
                            <tr>
                              <td class="columnContainer" style="mso-line-height-rule:
                                exactly;-ms-text-size-adjust:
                                100%;-webkit-text-size-adjust: 100%;" valign="top">
                                <table class="mcnImageBlock" style="min-width:
                                  100%;border-collapse:
                                  collapse;mso-table-lspace:
                                  0pt;mso-table-rspace:
                                  0pt;-ms-text-size-adjust:
                                  100%;-webkit-text-size-adjust: 100%;" border="0" cellpadding="0" cellspacing="0" width="100%">
                                  <tbody class="mcnImageBlockOuter">
                                    <tr>
                                      <td style="padding:
                                        9px;mso-line-height-rule:
                                        exactly;-ms-text-size-adjust:
                                        100%;-webkit-text-size-adjust:
                                        100%;" class="mcnImageBlockInner" valign="top">
                                        <table class="mcnImageContentContainer" style="min-width:
                                          100%;border-collapse:
                                          collapse;mso-table-lspace:
                                          0pt;mso-table-rspace:
                                          0pt;-ms-text-size-adjust:
                                          100%;-webkit-text-size-adjust:
                                          100%;" border="0" cellpadding="0" cellspacing="0" align="left" width="100%">
                                          <tbody>
                                            <tr>
                                              <td class="mcnImageContent" style="padding-right:
                                                9px;padding-left:
                                                9px;padding-top:
                                                0;padding-bottom:
                                                0;text-align:
                                                center;mso-line-height-rule:
exactly;-ms-text-size-adjust: 100%;-webkit-text-size-adjust: 100%;" valign="top"> <a moz-do-not-send="true" href="http://www.bink.com/how-to-add-payment-card" title="" class="" target="_blank" style="mso-line-height-rule:
exactly;-ms-text-size-adjust: 100%;-webkit-text-size-adjust: 100%;"> <img moz-do-not-send="true" alt="" src="https://gallery.mailchimp.com/ec044a65c525952557abbcb26/images/91c714d0-02df-401f-b430-e28195eb3983.jpg" style="max-width:
                                                    1800px;padding-bottom:
                                                    0;display: inline
                                                    !important;vertical-align:
                                                    bottom;border:
                                                    0;height:
                                                    auto;outline:
                                                    none;text-decoration:
none;-ms-interpolation-mode: bicubic;" class="mcnImage" align="middle" width="164"> </a> </td>
                                            </tr>
                                          </tbody>
                                        </table>
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
                        0px;padding-bottom: 0px;" valign="top">
                        <table class="mcnImageGroupBlock" style="border-collapse:
                          collapse;mso-table-lspace:
                          0pt;mso-table-rspace:
                          0pt;-ms-text-size-adjust:
                          100%;-webkit-text-size-adjust: 100%;" border="0" cellpadding="0" cellspacing="0" width="100%">
                          <tbody class="mcnImageGroupBlockOuter">
                            <tr>
                              <td style="padding:
                                9px;mso-line-height-rule:
                                exactly;-ms-text-size-adjust:
                                100%;-webkit-text-size-adjust: 100%;" class="mcnImageGroupBlockInner" valign="top">
                                <table class="mcnImageGroupContentContainer" style="border-collapse:
                                  collapse;mso-table-lspace:
                                  0pt;mso-table-rspace:
                                  0pt;-ms-text-size-adjust:
                                  100%;-webkit-text-size-adjust: 100%;" border="0" cellpadding="0" cellspacing="0" align="left" width="273">
                                  <tbody>
                                    <tr>
                                      <td class="mcnImageGroupContent" style="padding-left:
                                        9px;padding-top:
                                        0;padding-bottom:
                                        0;mso-line-height-rule:
                                        exactly;-ms-text-size-adjust:
                                        100%;-webkit-text-size-adjust:
                                        100%;" valign="top"> <img moz-do-not-send="true" alt="" src="https://gallery.mailchimp.com/ec044a65c525952557abbcb26/images/ba9827bc-d4f0-4eed-b669-78cba7dde7a8.jpg" style="max-width:
                                          1800px;padding-bottom:
                                          0;border: 0;height:
                                          auto;outline:
                                          none;text-decoration:
                                          none;-ms-interpolation-mode:
                                          bicubic;vertical-align:
                                          bottom;" class="mcnImage" width="264"> </td>
                                    </tr>
                                  </tbody>
                                </table>
                                <table class="mcnImageGroupContentContainer" style="border-collapse:
                                  collapse;mso-table-lspace:
                                  0pt;mso-table-rspace:
                                  0pt;-ms-text-size-adjust:
                                  100%;-webkit-text-size-adjust: 100%;" border="0" cellpadding="0" cellspacing="0" align="right" width="273">
                                  <tbody>
                                    <tr>
                                      <td class="mcnImageGroupContent" style="padding-right:
                                        9px;padding-top:
                                        0;padding-bottom:
                                        0;mso-line-height-rule:
                                        exactly;-ms-text-size-adjust:
                                        100%;-webkit-text-size-adjust:
                                        100%;" valign="top"> <img moz-do-not-send="true" alt="" src="https://gallery.mailchimp.com/ec044a65c525952557abbcb26/images/3df0877f-d1fd-4689-9d65-9b7b7e0b96b7.jpg" style="max-width:
                                          1800px;padding-bottom:
                                          0;border: 0;height:
                                          auto;outline:
                                          none;text-decoration:
                                          none;-ms-interpolation-mode:
                                          bicubic;vertical-align:
                                          bottom;" class="mcnImage" width="264"> </td>
                                    </tr>
                                  </tbody>
                                </table>
                              </td>
                            </tr>
                          </tbody>
                        </table>
                      </td>
                    </tr>
                    <tr>
                      <td id="templateLowerColumns" style="background:#ffffff none no-repeat
                        center/cover;mso-line-height-rule:
                        exactly;-ms-text-size-adjust:
                        100%;-webkit-text-size-adjust:
                        100%;background-color: #ffffff;background-image:
                        none;background-repeat:
                        no-repeat;background-position:
                        center;background-size: cover;border-top:
                        0;border-bottom: 2px solid #EAEAEA;padding-top:
                        10px;padding-bottom: 10px;" valign="top">
                        <!--[if gte mso 9]>
									<table align="center" border="0" cellspacing="0" cellpadding="0" width="600" style="width:600px;">
									<tr>
									<td align="center" valign="top" width="200" style="width:200px;">
									<![endif]-->
                        <table class="columnWrapper" style="border-collapse:
                          collapse;mso-table-lspace:
                          0pt;mso-table-rspace:
                          0pt;-ms-text-size-adjust:
                          100%;-webkit-text-size-adjust: 100%;" border="0" cellpadding="0" cellspacing="0" align="left" width="200">
                          <tbody>
                            <tr>
                              <td class="columnContainer" style="mso-line-height-rule:
                                exactly;-ms-text-size-adjust:
                                100%;-webkit-text-size-adjust: 100%;" valign="top">
                                <table class="mcnImageBlock" style="min-width:
                                  100%;border-collapse:
                                  collapse;mso-table-lspace:
                                  0pt;mso-table-rspace:
                                  0pt;-ms-text-size-adjust:
                                  100%;-webkit-text-size-adjust: 100%;" border="0" cellpadding="0" cellspacing="0" width="100%">
                                  <tbody class="mcnImageBlockOuter">
                                    <tr>
                                      <td style="padding:
                                        9px;mso-line-height-rule:
                                        exactly;-ms-text-size-adjust:
                                        100%;-webkit-text-size-adjust:
                                        100%;" class="mcnImageBlockInner" valign="top">
                                        <table class="mcnImageContentContainer" style="min-width:
                                          100%;border-collapse:
                                          collapse;mso-table-lspace:
                                          0pt;mso-table-rspace:
                                          0pt;-ms-text-size-adjust:
                                          100%;-webkit-text-size-adjust:
                                          100%;" border="0" cellpadding="0" cellspacing="0" align="left" width="100%">
                                          <tbody>
                                            <tr>
                                              <td class="mcnImageContent" style="padding-right:
                                                9px;padding-left:
                                                9px;padding-top:
                                                0;padding-bottom:
                                                0;text-align:
                                                center;mso-line-height-rule:
exactly;-ms-text-size-adjust: 100%;-webkit-text-size-adjust: 100%;" valign="top"> <a moz-do-not-send="true" href="https://www.facebook.com/hellobink" title="" class="" target="_blank" style="mso-line-height-rule:
exactly;-ms-text-size-adjust: 100%;-webkit-text-size-adjust: 100%;"> <img moz-do-not-send="true" alt="" src="https://gallery.mailchimp.com/ec044a65c525952557abbcb26/images/3e294902-30d4-4993-b1d7-6a32e45065ea.jpg" style="max-width:
                                                    2000px;padding-bottom:
                                                    0;display: inline
                                                    !important;vertical-align:
                                                    bottom;border:
                                                    0;height:
                                                    auto;outline:
                                                    none;text-decoration:
none;-ms-interpolation-mode: bicubic;" class="mcnImage" align="middle" width="164"> </a> </td>
                                            </tr>
                                          </tbody>
                                        </table>
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
									<td align="center" valign="top" width="200" style="width:200px;">
									<![endif]-->
                        <table class="columnWrapper" style="border-collapse:
                          collapse;mso-table-lspace:
                          0pt;mso-table-rspace:
                          0pt;-ms-text-size-adjust:
                          100%;-webkit-text-size-adjust: 100%;" border="0" cellpadding="0" cellspacing="0" align="left" width="200">
                          <tbody>
                            <tr>
                              <td class="columnContainer" style="mso-line-height-rule:
                                exactly;-ms-text-size-adjust:
                                100%;-webkit-text-size-adjust: 100%;" valign="top">
                                <table class="mcnImageBlock" style="min-width:
                                  100%;border-collapse:
                                  collapse;mso-table-lspace:
                                  0pt;mso-table-rspace:
                                  0pt;-ms-text-size-adjust:
                                  100%;-webkit-text-size-adjust: 100%;" border="0" cellpadding="0" cellspacing="0" width="100%">
                                  <tbody class="mcnImageBlockOuter">
                                    <tr>
                                      <td style="padding:
                                        9px;mso-line-height-rule:
                                        exactly;-ms-text-size-adjust:
                                        100%;-webkit-text-size-adjust:
                                        100%;" class="mcnImageBlockInner" valign="top">
                                        <table class="mcnImageContentContainer" style="min-width:
                                          100%;border-collapse:
                                          collapse;mso-table-lspace:
                                          0pt;mso-table-rspace:
                                          0pt;-ms-text-size-adjust:
                                          100%;-webkit-text-size-adjust:
                                          100%;" border="0" cellpadding="0" cellspacing="0" align="left" width="100%">
                                          <tbody>
                                            <tr>
                                              <td class="mcnImageContent" style="padding-right:
                                                9px;padding-left:
                                                9px;padding-top:
                                                0;padding-bottom:
                                                0;text-align:
                                                center;mso-line-height-rule:
exactly;-ms-text-size-adjust: 100%;-webkit-text-size-adjust: 100%;" valign="top"> <a moz-do-not-send="true" href="https://www.twitter.com/hellobink" title="" class="" target="_blank" style="mso-line-height-rule:
exactly;-ms-text-size-adjust: 100%;-webkit-text-size-adjust: 100%;"> <img moz-do-not-send="true" alt="" src="https://gallery.mailchimp.com/ec044a65c525952557abbcb26/images/8270aa9d-4ec5-4cfa-b0d9-4ffb4b31c962.jpg" style="max-width:
                                                    2000px;padding-bottom:
                                                    0;display: inline
                                                    !important;vertical-align:
                                                    bottom;border:
                                                    0;height:
                                                    auto;outline:
                                                    none;text-decoration:
none;-ms-interpolation-mode: bicubic;" class="mcnImage" align="middle" width="164"> </a> </td>
                                            </tr>
                                          </tbody>
                                        </table>
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
									<td align="center" valign="top" width="200" style="width:200px;">
									<![endif]-->
                        <table class="columnWrapper" style="border-collapse:
                          collapse;mso-table-lspace:
                          0pt;mso-table-rspace:
                          0pt;-ms-text-size-adjust:
                          100%;-webkit-text-size-adjust: 100%;" border="0" cellpadding="0" cellspacing="0" align="left" width="200">
                          <tbody>
                            <tr>
                              <td class="columnContainer" style="mso-line-height-rule:
                                exactly;-ms-text-size-adjust:
                                100%;-webkit-text-size-adjust: 100%;" valign="top">
                                <table class="mcnImageBlock" style="min-width:
                                  100%;border-collapse:
                                  collapse;mso-table-lspace:
                                  0pt;mso-table-rspace:
                                  0pt;-ms-text-size-adjust:
                                  100%;-webkit-text-size-adjust: 100%;" border="0" cellpadding="0" cellspacing="0" width="100%">
                                  <tbody class="mcnImageBlockOuter">
                                    <tr>
                                      <td style="padding:
                                        9px;mso-line-height-rule:
                                        exactly;-ms-text-size-adjust:
                                        100%;-webkit-text-size-adjust:
                                        100%;" class="mcnImageBlockInner" valign="top">
                                        <table class="mcnImageContentContainer" style="min-width:
                                          100%;border-collapse:
                                          collapse;mso-table-lspace:
                                          0pt;mso-table-rspace:
                                          0pt;-ms-text-size-adjust:
                                          100%;-webkit-text-size-adjust:
                                          100%;" border="0" cellpadding="0" cellspacing="0" align="left" width="100%">
                                          <tbody>
                                            <tr>
                                              <td class="mcnImageContent" style="padding-right:
                                                9px;padding-left:
                                                9px;padding-top:
                                                0;padding-bottom:
                                                0;text-align:
                                                center;mso-line-height-rule:
exactly;-ms-text-size-adjust: 100%;-webkit-text-size-adjust: 100%;" valign="top"> <a moz-do-not-send="true" href="mailto:support@bink.com?subject=Bink%20App%20Support%20Request" title="" class="" target="_blank" style="mso-line-height-rule:
exactly;-ms-text-size-adjust: 100%;-webkit-text-size-adjust: 100%;"> <img moz-do-not-send="true" alt="" src="https://gallery.mailchimp.com/ec044a65c525952557abbcb26/images/5d0da906-9b75-4fae-b8f8-416c30ddbdb6.jpg" style="max-width:
                                                    2000px;padding-bottom:
                                                    0;display: inline
                                                    !important;vertical-align:
                                                    bottom;border:
                                                    0;height:
                                                    auto;outline:
                                                    none;text-decoration:
none;-ms-interpolation-mode: bicubic;" class="mcnImage" align="middle" width="164"> </a> </td>
                                            </tr>
                                          </tbody>
                                        </table>
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
									</tr>
									</table>
									<![endif]--> </td>
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
                        0px;padding-bottom: 0px;" valign="top">
                        <table class="mcnDividerBlock" style="min-width:
                          100%;border-collapse:
                          collapse;mso-table-lspace:
                          0pt;mso-table-rspace:
                          0pt;-ms-text-size-adjust:
                          100%;-webkit-text-size-adjust:
                          100%;table-layout: fixed !important;" border="0" cellpadding="0" cellspacing="0" width="100%">
                          <tbody class="mcnDividerBlockOuter">
                            <tr>
                              <td class="mcnDividerBlockInner" style="min-width: 100%;padding: 10px
                                18px;mso-line-height-rule:
                                exactly;-ms-text-size-adjust:
                                100%;-webkit-text-size-adjust: 100%;">
                                <table class="mcnDividerContent" style="min-width:
                                  100%;border-top-width:
                                  2px;border-top-style:
                                  none;border-top-color:
                                  #EAEAEA;border-collapse:
                                  collapse;mso-table-lspace:
                                  0pt;mso-table-rspace:
                                  0pt;-ms-text-size-adjust:
                                  100%;-webkit-text-size-adjust: 100%;" border="0" cellpadding="0" cellspacing="0" width="100%">
                                  <tbody>
                                    <tr>
                                      <td style="mso-line-height-rule:
                                        exactly;-ms-text-size-adjust:
                                        100%;-webkit-text-size-adjust:
                                        100%;"> <span></span> <br>
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
                        <table class="mcnTextBlock" style="min-width:
                          100%;border-collapse:
                          collapse;mso-table-lspace:
                          0pt;mso-table-rspace:
                          0pt;-ms-text-size-adjust:
                          100%;-webkit-text-size-adjust: 100%;" border="0" cellpadding="0" cellspacing="0" width="100%">
                          <tbody class="mcnTextBlockOuter">
                            <tr>
                              <td class="mcnTextBlockInner" style="padding-top:
                                9px;mso-line-height-rule:
                                exactly;-ms-text-size-adjust:
                                100%;-webkit-text-size-adjust: 100%;" valign="top">
                                <!--[if mso]>
				<table align="left" border="0" cellspacing="0" cellpadding="0" width="100%" style="width:100%;">
				<tr>
				<![endif]-->
                                <!--[if mso]>
				<td valign="top" width="600" style="width:600px;">
				<![endif]-->
                                <table style="max-width: 100%;min-width:
                                  100%;border-collapse:
                                  collapse;mso-table-lspace:
                                  0pt;mso-table-rspace:
                                  0pt;-ms-text-size-adjust:
                                  100%;-webkit-text-size-adjust: 100%;" class="mcnTextContentContainer" border="0" cellpadding="0" cellspacing="0" align="left" width="100%">
                                  <tbody>
                                    <tr>
                                      <td class="mcnTextContent" style="padding-top:
                                        0;padding-right:
                                        18px;padding-bottom:
                                        9px;padding-left:
                                        18px;mso-line-height-rule:
                                        exactly;-ms-text-size-adjust:
                                        100%;-webkit-text-size-adjust:
                                        100%;word-break:
                                        break-word;color:
                                        #656565;font-family:
                                        Helvetica;font-size:
                                        12px;line-height:
                                        150%;text-align: center;" valign="top">
                                        <div style="text-align: center;"><em>Copyright
                                            © 2016 Bink, All rights
                                            reserved.</em><br>
                                          <br>
                                          <strong>Our mailing address
                                            is:</strong><br>
                                          Second Floor, 2 Queens
                                          Square,&nbsp;Lyndhurst
                                          Road,&nbsp;Ascot,&nbsp;Berkshire,&nbsp;SL5
                                          9FE<br>
                                          Don't want to receive awesome
                                          emails from us?&nbsp;You can&nbsp;<a moz-do-not-send="true" href="mailto:support@bink.com?subject=Unsubscribe%20from%20Marketing&amp;body=Please%20unsubscribe%20me%20from%20Bink%20Marketing" target="_blank" style="mso-line-height-rule:
exactly;-ms-text-size-adjust: 100%;-webkit-text-size-adjust: 100%;color:
                                            #656565;font-weight:
                                            normal;text-decoration:
                                            underline;">unsubscribe here</a></div>
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
						<![endif]-->
                <!-- // END TEMPLATE --> </td>
            </tr>
          </tbody>
        </table>
      </center>
    </div>
  </body>

{% endblock %}
