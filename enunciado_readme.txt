# Prueba técnica: Mini backtester intradía                                                                                                                                                               
																																																	   
Queremos que desarrolles una aplicación sencilla que permita simular y analizar una estrategia básica de trading entre sesiones intradía.                                                                
																																																	   
## Datos                                                                                                                                                                                                 
Te facilitamos varios datasets históricos del mercado eléctrico francés en 2025.																																																   
Dispondrás de los siguientes datasets exportados:                                                                                                                                                        
- spot_price                                                                                                                                                                                             
- intraday_session
- mic_trades                                                                                                                                                                                       
- imbalance
																																																	   
## Objetivo                                                                                                                                                                                             
Construir una solución con backend y frontend que permita:                                                                                                                                           
																																																	   
- seleccionar un rango temporal,                                                                                                                                                                         
- ejecutar una estrategia simple entre S0, IDA1, IDA2 e IDA3,                                                                                                                                            
- visualizar los trades generados,                                                                                                                                                                       
- mostrar métricas básicas de performance.                                                                                                                                                               
																																																	   
## Qué valoramos                                                                                                                                                                                         
																																																	   
Nos interesa especialmente:                                                                                                                                                                              
																																																	   
- cómo modelas el problema,                                                                                                                                                                              
- qué supuestos haces,                                                                                                                                                                                   
- cómo razonas sobre qué datos están disponibles en cada momento,                                                                                                                                        
- cómo evitas sesgos como look-ahead bias,                                                                                                                                                               
- cómo representas trades, PnL y métricas,                                                                                                                                                               
- cómo explicas limitaciones y decisiones de diseño.                                                                                                                                                     
																																																	   
No buscamos una solución perfecta ni una estrategia “ganadora”. Priorizamos una solución simple, coherente y bien razonada.                                                                              
																																																	   
## Alcance esperado                                                                                                                                                                                     
Esperamos una implementación mínima pero funcional.                                                                                                                                                    																																				   
Puedes simplificar libremente siempre que expliques tus supuestos, justifiques tus decisiones y dejes claras las limitaciones de tu enfoque.    																																					   

																																														   
## Entregables                                                                                                                                                                                           
																																																	   
- código fuente                                                                                                                                                                                         
- instrucciones de ejecución                                                                                                                                                                           
- README breve con:                                                                                                                                                                                      
  - arquitectura,                                                                                                                                                                                      
  - supuestos,                                                                                                                                                                                         
  - estrategia implementada,                                                                                                                                                                           
  - limitaciones,                                                                                                                                                                                      
  - qué harías con más tiempo                                                                                                                                                                         
																																																	   
## Dinámica 																																												   
La prueba tendrá dos fases:                                                                                                                                                                              
																																																	   
1. Una primera fase de 2 horas, tras la cual tendremos una llamada corta para revisar tu enfoque, el estado de la solución y tus decisiones técnicas.                                                    
2. Después de esa llamada, dispondrás de hasta 24 horas adicionales para completar y entregar la versión final.                                                                                          
																																																	   
## Bonus opcional
Si te da tiempo:
 - Generaliza la solución para permitir al usuario generar estrategias desde el frontend
 - Extiende la solución para incorporar el MIC como trading venue, y/o datos de imbalance para generar señales.
 