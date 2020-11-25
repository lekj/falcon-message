package main

import (
	"bytes"
	"errors"
	"log"
	"net/http"
	"path"
	"strings"
	"text/template"
	"time"

	"github.com/labstack/echo"
	"github.com/labstack/echo/middleware"
	"github.com/lekj/falcon-message/config"
	"github.com/lekj/falcon-message/sender"
	"github.com/lekj/falcon-message/util"
	"github.com/tylerb/graceful"
)

// OK
// P3
// Endpoint:SMARTMATRIX_MONITOR
// Metric:api
// Tags:act=webapi.bindDevice,loc=GZ
// all(#2): 1==0
// Note:act=webapi.bindDevice,loc=GZ
// Max:3, Current:1
// Timestamp:2017-06-02 08:02:00
// http://127.0.0.1:8081/portal/template/view/37

const (
	// IMDingPrefix 钉钉 前缀
	IMDingPrefix = "[ding]:"
	// IMWexinPrefix 微信前缀
	// IMWexinPrefix = "[wexin]:"
)

var (
	cfg    config.Config
	ding   *sender.DingTalk
	wx     *sender.Weixin
	tpl    *template.Template
	tpl_wx *template.Template
)

func main() {

	cfg = config.Read()
	funcMap := template.FuncMap{"elapse": func(count, reportInterval, triggerCount, postpone int) int {
		// 都使用 秒计算
		// 超过1次，要计算推迟时间
		if count > 1 {
			return reportInterval*triggerCount + postpone*(count-1)
		}

		// 第一次，直接返回上报间隔
		return reportInterval * triggerCount
	}, "divide": func(a, b int) int { return a / b },
		"timeFormat": func(t time.Time, format string) string {
			return t.Format(format)
		},
		"timeDiffFormat": func(t time.Time, format string, seconds int) string {
			return t.Add(-(time.Second * time.Duration(seconds))).Format(format)
		}}

	tpl = template.Must(template.New(path.Base(cfg.DingTalk.TemplateFile)).Funcs(funcMap).ParseFiles(cfg.DingTalk.TemplateFile))
	tpl_wx = template.Must(template.New(path.Base(cfg.Weixin.TemplateFile)).Funcs(funcMap).ParseFiles(cfg.Weixin.TemplateFile))

	if cfg.DingTalk.Enable {
		ding = sender.NewDingTalk()
	}

	// log.Println("cfg Weixin Enable:", cfg.Weixin.Enable )
	log.Println("cfg Weixin CorpID:", cfg.Weixin.CorpID, ",Secret:", cfg.Weixin.Secret, ", agentId:", cfg.Weixin.AgentID)
	if cfg.Weixin.Enable {
		wx = sender.NewWeixin(cfg.Weixin.CorpID, cfg.Weixin.Secret, cfg.Weixin.AgentID)
		// log.Println("go wx:", &wx)
		go wx.GetAccessToken()
		// log.Println("go wx.GetToken end")
	}

	engine := echo.New()
	engine.Server.Addr = cfg.Addr
	server := &graceful.Server{Timeout: time.Second * 10, Server: engine.Server, Logger: graceful.DefaultLogger()}
	engine.Use(middleware.Recover())
	// engine.Use(middleware.Logger())
	api := engine.Group("/api/v1")
	api.GET("/wechat/auth", wxAuth)
	api.POST("/message", func(c echo.Context) error {

		log.Println("message comming")
		tos := c.FormValue("tos")
		content_wx := c.FormValue("content_wx")
		content := c.FormValue("content")
		subject := c.FormValue("subject")
		log.Println("tos:", tos, " content:", content, " subject:", subject)

		if content == "" {
			return echo.NewHTTPError(http.StatusBadRequest, "content is requied")
		}
		if content_wx == "" {
			return echo.NewHTTPError(http.StatusBadRequest, "content is requied")
		}

		if subject == "" {
			subject = "服务器告警"
		}

		var buffer bytes.Buffer
		var buffer_wx bytes.Buffer

		// log.Println( strings.Index(subject, "日常报告") )
		if strings.Index(subject, "日常报告") < 0 {
			msg, err := util.HandleContent(content)
			if err != nil {
				return err
			}

			if err = tpl_wx.Execute(&buffer, msg); err != nil {
				return err
			}
			content = buffer.String()

			msg_wx, err_wx := util.HandleContent(content_wx)
			if err_wx != nil {
				return err
			}

			if err_wx = tpl.Execute(&buffer_wx, msg_wx); err_wx != nil {
				return err
			}
			content_wx = buffer_wx.String()
		} else {
			//dd_content = "## " + subject + "\n\n " + strings.Replace(strings.Replace(strings.Replace(content, "\n", "\n- ", -1), "- # 服务器", "# 服务器", -1), "- \n- ---", "---", -1)
			//log.Println("dd content:", dd_content)
		}

		var weixin_token strings.Builder //微信 把微信的帐号拼接起来，一次发送。
		if cfg.Weixin.Enable {
			for _, v := range strings.Split(tos, ",") {
				if len(v) > 0 && !strings.HasPrefix(v, IMDingPrefix) {
					if weixin_token.Len() > 0 {
						weixin_token.WriteString(",")
					}
					weixin_token.WriteString(v)
				}
			}
		}

		log.Println("weixin token:", weixin_token)

		if cfg.Weixin.Enable {
			if weixin_token.Len() > 0 {
				if err := wx.Send(weixin_token.String(), content_wx, subject); err != nil {
					//return echo.NewHTTPError(500, err.Error())
					log.Println("ERR:", err.Error())
				}
			}
		}

		//if cfg.Weixin.Enable {
		//    if( weixin_token.Len() > 0 ){
		//        kov := strings.Split( content, "\n---\n" )
		//        log.Println( "len kov:", len( kov ), ", kov:" , kov );
		//        if len( kov ) <= 0 {
		//            if err := wx.Send(weixin_token.String(), content, subject ); err != nil {
		//                //return echo.NewHTTPError(500, err.Error())
		//                log.Println("ERR:", err.Error())
		//            }
		//        } else {
		//            for i := 0; i < len( kov ) ; i++ {
		//                if ( strings.Replace( strings.Replace(kov[ i ], "\n", "", -1 ) , " ", "", -1) ) != "" {
		//                    cont:= strip( kov[ i ], "/ \n\r\t" )
		//                    // log.Println( "cont:", cont )
		//                    idx := strings.Index( cont, "\n" )
		//                    lvv := len( cont )
		//                    serverName := string( cont[ 2 : idx ] )
		//                    sendtext   := string( cont[ idx + 1 : lvv ] )
		//                    log.Println("s:",serverName," x:",sendtext )
		//
		//                    if len( serverName ) > 0 && len( sendtext ) >0 {
		//                        new_subject := strings.Replace( subject, "日常报告", ""+ strings.Replace( serverName, "# ", "", 1 ) + " 日常报告", -1 )
		//
		//                        log.Println( "new_subject:", new_subject )
		//                        if err := wx.Send(weixin_token.String(), sendtext, new_subject ); err != nil {
		//                            //return echo.NewHTTPError(500, err.Error())
		//                            log.Println("ERR:", err.Error())
		//                        }
		//                    }
		//                }
		//            }
		//        }
		//    }
		//}

		//content = "## " + subject + "\n\n " + strings.Replace(strings.Replace(strings.Replace(content, "\n", "\n- ", -1), "- # 主机", "# 主机", -1), "- \n- ---", "---", -1)
		for _, v := range strings.Split(tos, ",") {
			go func(onetoken string) {
				// log.Println("one token:", onetoken )
				if strings.HasPrefix(onetoken, IMDingPrefix) { //是钉钉
					token := onetoken[len(IMDingPrefix):]
					log.Println("ding ding token:", token)
					if cfg.DingTalk.Enable {
						if err := ding.Send(token, content, cfg.DingTalk.MessageType); err != nil {
							log.Println("ERR:", err)
						}
					}
				}
			}(v)
		}

		return nil
	})

	log.Println("end listening on ", cfg.Addr)
	if err := server.ListenAndServe(); err != nil {
		log.Fatal(err)
	}
}

//func strip(s_ string, chars_ string) string {
//    s, chars := []rune(s_), []rune(chars_)
//    length := len(s)
//    max := len(s) - 1
//    l, r := true, true //标记当左端或者右端找到正常字符后就停止继续寻找
//    start, end := 0, max
//    tmpEnd := 0
//    charset := make(map[rune]bool) //创建字符集，也就是唯一的字符，方便后面判断是否存在
//    for i := 0; i < len(chars); i++ {
//        charset[chars[i]] = true
//    }
//    for i := 0; i < length; i++ {
//        if _, exist := charset[s[i]]; l && !exist {
//            start = i
//            l = false
//        }
//        tmpEnd = max - i
//        if _, exist := charset[s[tmpEnd]]; r && !exist {
//            end = tmpEnd
//            r = false
//        }
//        if !l && !r {
//            break
//        }
//    }
//    if l && r { // 如果左端和右端都没找到正常字符，那么表示该字符串没有正常字符
//        return ""
//    }
//    return string(s[start : end+1])
//}

// WxAuth 开启回调模式验证
func wxAuth(context echo.Context) error {
	if cfg.Weixin.Enable {
		echostr := context.FormValue("echostr")
		if echostr == "" {
			return errors.New("无法获取请求参数, echostr 为空")
		}
		var buf []byte
		var err error
		if buf, err = wx.Auth(echostr); err != nil {
			return err
		}

		return context.JSONBlob(200, buf)
	}

	return context.String(200, "微信没有启用")
}
